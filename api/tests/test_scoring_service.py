"""Remaining scoring service/rules contracts; actual score replacement SQL."""
import unittest
from actors import UserActor
from endpoints.scoring.service import ScoringService
from endpoints.scoring.rules import playoff_depth_bonus, conference_champion_bonus, conference_bottom_bonus
from endpoints.scoring.contracts import ScoringReadDenied
import test_scoring_authorization as authorization
from test_league_read_authorization import ReadDatabase


class PresetWeeklyService(ScoringService):
    def _get_week_by_number(self,league_id,week_number):
        return {'id':100,'weekNumber':week_number}
    def _get_league_members(self,league_id):
        return [{'id':1,'teamName':'A'},{'id':2,'teamName':'B'}]
    def compute_member_point_diff_for_week(self,league_id,member_id,week_number):
        return {1:5,2:-2}[member_id]
    def apply_weekly_tiebreakers(self,league_id,week_number,members):
        return members


class RemainingScoringServiceTests(unittest.TestCase):
    def setUp(self):
        self.db=ReadDatabase()
        self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''CREATE TABLE WeeklyTeamScore (
            leagueId INTEGER,weekId INTEGER,memberId INTEGER,pointDifferential INTEGER,rank INTEGER,pointsAwarded INTEGER);
            INSERT INTO WeeklyTeamScore VALUES (33,100,1,99,1,2),(33,100,2,88,2,1),
                (44,100,1,77,1,1),(33,200,1,66,1,1);''')
        self.service=PresetWeeklyService(self.db,None)

    def rows(self):
        return [tuple(r) for r in self.db.connection.execute('SELECT * FROM WeeklyTeamScore ORDER BY leagueId,weekId,memberId')]

    def test_week_zero_replacement_is_scoped_and_repeated_run_converges(self):
        for _ in range(2):
            result=self.service.compute_weekly_scores_for_job(33,0)
            self.assertEqual(result['weekNumber'],0)
            self.assertEqual(self.rows(),[(33,100,1,5,1,2),(33,100,2,-2,2,1),(33,200,1,66,1,1),(44,100,1,77,1,1)])

    def test_failure_during_second_insert_preserves_entire_previous_set(self):
        before=self.rows()
        inserts=0
        def fail(sql):
            nonlocal inserts
            if 'INSERT INTO "WeeklyTeamScore"' in sql:
                inserts+=1
                if inserts==2: raise RuntimeError('injected second insert failure')
        self.db.before_query=fail
        with self.assertRaisesRegex(RuntimeError,'second insert'):
            self.service.compute_weekly_scores_for_job(33,0)
        self.db.before_query=None
        self.assertEqual(self.rows(),before)

    def test_season_interactive_actor_required_before_io(self):
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):
                self.service.get_season_standings(actor,33)

    def test_pure_bonus_awards_preserve_ties_positions_and_zero_exclusions(self):
        self.assertEqual(playoff_depth_bonus({1:3,2:3,3:0},[1,2,3],{'first':3,'third':1}),{1:3.0,2:3.0,3:0.0})
        self.assertEqual(conference_champion_bonus({1:2,2:0,3:1},[1,2,3],{'first':2,'second':1.5,'third':1}),{1:2.0,2:0.0,3:1.5})
        self.assertEqual(conference_bottom_bonus({1:-5,2:-5,3:0},[1,2,3],{'last':-1.5,'thirdLast':-0.5}),{1:-1.5,2:-1.5,3:0.0})


class SeasonServiceAuthorizationTests(unittest.TestCase):
    def setUp(self):
        base=authorization.ScoringAuthorizationTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db=base.db
        self.service=ScoringService(self.db,None)

    def test_actor_standings_and_trusted_standings_preserve_projection(self):
        own=self.service.get_season_standings(UserActor(2,'member'),10)
        self.assertEqual([r['totalPoints'] for r in own['members']],[2.0,1.0])
        self.assertEqual(self.service.get_season_standings_for_job(20)['members'][0]['weeklyPoints'],8.0)
        with self.assertRaises(ScoringReadDenied):
            self.service.get_season_standings(UserActor(3,'outsider'),10)

    def test_revocation_during_standings_suppresses_private_results(self):
        def revoke(sql):
            if 'WeeklyTeamScore' in sql:
                self.db.before_query=None
                self.db.connection.execute('DELETE FROM LeagueMember WHERE id=12')
        self.db.before_query=revoke
        with self.assertRaises(ScoringReadDenied):
            self.service.get_season_standings(UserActor(2,'member'),10)

class NativeRowScoringTests(unittest.TestCase):
    def setUp(self):
        from sqlalchemy.engine.result import result_tuple
        from endpoints.scoring.repository import ScoringRepository
        def row(keys,values):
            return result_tuple(keys)(values)
        class StoredFacts(ScoringRepository):
            def sport_season(self,conn,league_id):
                return row(['sportSeasonId','sportId','seasonYear'],[1,1,2026])
            def primary_phases(self,conn,sport_season_id,primary_types):
                return [row(['id'],[10])]
            def owned_teams(self,conn,league_id,member_id):
                return [row(['sportTeamId'],[100+member_id])]
            def playoff_depth(self,conn,sport_season_id,phase_ids,team_ids):
                return row(['max_round'],[3 if team_ids==[101] else 2])
            def weeks_descending(self,conn,league_id):
                return [row(['id','weekNumber'],[100,1])]
            def weekly_ranks(self,conn,league_id,week_id,member_ids):
                return [row(['memberId','rank'],[1,2]),row(['memberId','rank'],[2,1])]
        self.db=ReadDatabase()
        self.addCleanup(self.db.connection.close)
        self.service=ScoringService(self.db,None,StoredFacts())
        self.group=[{'memberId':1,'totalPoints':2},{'memberId':2,'totalPoints':2}]

    def test_playoff_bonus_facts_read_real_sqlalchemy_row_mapping(self):
        self.assertEqual(self.service._get_playoff_depth_by_member(10,[1,2]),{1:3,2:2})

    def test_playoff_tiebreak_reads_real_sqlalchemy_row_mapping(self):
        self.assertEqual([m['memberId'] for m in self.service._tb_season_playoff_depth(10,self.group)],[1,2])

    def test_latest_week_tiebreak_reads_real_sqlalchemy_row_mapping(self):
        self.assertEqual([m['memberId'] for m in self.service._tb_season_latest_non_tied_week(10,self.group)],[2,1])
