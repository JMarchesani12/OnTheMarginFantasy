import datetime as dt
import unittest
from endpoints.scoring.bonus_service import SeasonBonusService
from test_league_read_authorization import ReadDatabase

class Facts:
    def context(self,conn,league_id): return {'sportSeasonId':1,'weekNumber':3}
    def roster(self,conn,league_id,week_number):
        return [{'memberId':1,'sportTeamId':10,'sportConferenceId':7}, {'memberId':1,'sportTeamId':11,'sportConferenceId':7}, {'memberId':1,'sportTeamId':12,'sportConferenceId':7}]
    def snapshots(self,conn,season_id):
        return [{'id':8,'sportConferenceId':7,'entries':[{'sportTeamId':10,'rank':1,'bottomRank':10},{'sportTeamId':11,'rank':2,'bottomRank':9},{'sportTeamId':12,'rank':10,'bottomRank':1}]}]
    def tournaments(self,conn,season_id): return []

class SeasonBonusServiceTests(unittest.TestCase):
    def test_conference_points_use_each_current_team_and_not_tournament_facts(self):
        facts=Facts();service=SeasonBonusService(facts)
        result=service.compute(None,1,[1,2],{'conferenceChampion':{'first':1.5,'second':1},'conferenceBottom':{'last':-1.5}})
        self.assertEqual(result['points'],{1:1,2:0})
        self.assertEqual(result['status']['state'],'ready');self.assertEqual(result['status']['snapshotIds'],[8])

    def test_missing_final_snapshot_is_pending_not_ready_zero(self):
        facts=Facts();facts.snapshots=lambda conn,season:[]
        result=SeasonBonusService(facts).compute(None,1,[1],{'conferenceChampion':{'first':1.5}})
        self.assertEqual(result['points'],{1:0});self.assertEqual(result['status']['state'],'pending')

    def test_no_mapping_is_pending(self):
        facts=Facts();facts.roster=lambda *args:[{'memberId':1,'sportTeamId':10,'sportConferenceId':None}]
        self.assertEqual(SeasonBonusService(facts).compute(None,1,[1],{'conferenceChampion':{'first':1.5}})['status']['state'],'pending')

class CurrentBonusOwnershipTests(unittest.TestCase):
    def test_old_owner_and_future_acquisition_do_not_receive_bonus(self):
        from endpoints.scoring.bonus_repository import SeasonBonusRepository
        db=ReadDatabase();self.addCleanup(db.connection.close)
        db.connection.create_function('now',0,lambda:'2026-11-10T12:00:00Z')
        db.connection.executescript('''
          CREATE TABLE League (id INTEGER,sport INTEGER,seasonYear INTEGER,settings TEXT);
          INSERT INTO League VALUES(1,1,2026,'{"subdivision":"FBS"}');
          CREATE TABLE SportSeason (id INTEGER,sportId INTEGER,seasonYear INTEGER);
          INSERT INTO SportSeason VALUES(1,1,2026);
          CREATE TABLE Week (leagueId INTEGER,weekNumber INTEGER,startDate TEXT);
          INSERT INTO Week VALUES(1,1,'2026-11-01'),(1,2,'2026-11-08'),(1,3,'2026-11-15');
          CREATE TABLE SportTeam(id INTEGER,sportId INTEGER); INSERT INTO SportTeam VALUES(10,1),(11,1);
          CREATE TABLE SportConference(id INTEGER,sportId INTEGER);INSERT INTO SportConference VALUES(7,1);
          CREATE TABLE ConferenceMembership(sportTeamId INTEGER,sportConferenceId INTEGER,sportId INTEGER,seasonYear INTEGER);
          INSERT INTO ConferenceMembership VALUES(10,7,1,2026),(11,7,1,2026);
          CREATE TABLE LeagueTeamSlot(leagueId INTEGER,memberId INTEGER,sportTeamId INTEGER,acquiredWeek INTEGER,droppedWeek INTEGER);
          INSERT INTO LeagueTeamSlot VALUES(1,1,10,1,2),(1,2,10,2,NULL),(1,1,11,3,NULL);
        ''')
        repo=SeasonBonusRepository();context=repo.context(db,1)
        self.assertEqual(context['weekNumber'],2)
        self.assertEqual(context['subdivision'],'FBS')
        self.assertEqual(repo.roster(db,1,2),[{'memberId':2,'sportTeamId':10,'sportConferenceId':7}])
        db.connection.execute("UPDATE Week SET startDate='2026-10-01'")
        self.assertEqual(repo.context(db,1)['weekNumber'],3)

class SeasonStandingsBonusIntegrationTests(unittest.TestCase):
    def fixture(self):
        from test_season_finalization import SeasonFinalizationTests
        base=SeasonFinalizationTests();base.setUp();self.addCleanup(base.doCleanups)
        base.db.connection.execute('UPDATE League SET settings=? WHERE id=10',('{"bonuses":{"conferenceChampion":{"first":1.5}}}',))
        facts=Facts();facts.roster=lambda *args:[{'memberId':11,'sportTeamId':10,'sportConferenceId':7}]
        base.scoring.bonus_service=SeasonBonusService(facts)
        return base

    def test_ready_bonuses_are_applied_only_when_final_scoreboard_runs(self):
        from actors import UserActor
        from test_season_finalization import NOW
        base=self.fixture()
        before=base.scoring.get_season_standings(UserActor(1,'commissioner'),10)
        self.assertEqual(before['members'][0]['bonusPoints'],0)
        self.assertEqual(before['members'][0]['totalPoints'],2)
        self.assertEqual(before['bonusStatus']['state'],'pending')
        self.assertEqual(base.service.run(NOW)['finalized'],[1,2])
        after=base.scoring.get_season_standings(UserActor(1,'commissioner'),10)
        self.assertEqual(after['members'][0]['bonusPoints'],1.5)
        self.assertEqual(after['members'][0]['totalPoints'],3.5)
        self.assertEqual(after['bonusStatus']['state'],'ready')

    def test_standings_reads_never_evaluate_bonus_data_even_after_season_end(self):
        base=self.fixture()
        def forbidden(*args,**kwargs): raise AssertionError('A standings read evaluated bonuses')
        base.scoring.bonus_service.compute=forbidden
        for read in (base.scoring.get_season_standings_for_job,):
            self.assertEqual(read(10)['members'][0]['bonusPoints'],0)

    def test_final_calculation_requires_the_finalizers_supplied_transaction(self):
        base=self.fixture()
        with self.assertRaises(TypeError): base.scoring.compute_final_season_standings_for_job(10,conn=None)
