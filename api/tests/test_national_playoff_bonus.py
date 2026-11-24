import unittest
from rules.nationalBonusIdentity import national_game_identity
from endpoints.scoring.bonus_service import SeasonBonusService
from test_season_bonus_service import Facts

class NationalIdentityTests(unittest.TestCase):
    def identity(self,label): return national_game_identity({'tournamentLabels':[label]})
    def test_verified_provider_labels_map_to_competition_and_round(self):
        cases=[("NCAA Men's Basketball Championship - West Region - 1st Round",('NCAA_TOURNEY',2)),
               ('College Football Playoff Quarterfinal at the Rose Bowl Presented by Prudential',('FBS_PLAYOFFS',2)),
               ('FCS Championship - Semifinals',('FCS_PLAYOFFS',4)),
               ('College Football Playoff National Championship',('FBS_PLAYOFFS',4)),
               ("NCAA Men's Basketball Championship - National Championship",('NCAA_TOURNEY',7))]
        for label,want in cases:
            with self.subTest(label=label): self.assertEqual(self.identity(label),want)
    def test_conference_titles_bowls_secondary_tournaments_and_missing_rounds_are_ineligible(self):
        for label in ['Big 12 Championship','SEC Championship','Rose Bowl','NIT - Championship','CIT Championship','Crown Championship',"NCAA Men's Basketball Championship"]:
            with self.subTest(label=label): self.assertEqual(self.identity(label),(None,None))

class PlayoffFacts(Facts):
    def roster(self,*args):
        return [{'memberId':1,'sportTeamId':10,'sportConferenceId':7},{'memberId':2,'sportTeamId':11,'sportConferenceId':7}]
    def tournaments(self,*args): return [{'id':20,'code':'FBS_PLAYOFFS','ended':True,'expectedRoundCounts':{4:1}}]
    def playoff_games(self,*args):
        return [{'homeTeamId':10,'awayTeamId':11,'homeScore':30,'awayScore':20,'roundOrder':4,'isCompleted':True,'bonusTournamentCode':'FBS_PLAYOFFS'}]

class NationalAwardTests(unittest.TestCase):
    def test_champion_outranks_runner_up_and_form_setting_works(self):
        result=SeasonBonusService(PlayoffFacts()).compute(None,1,[1,2],{'farthestInPlayoffs':{'farthest':3}})
        self.assertEqual(result['points'],{1:3,2:0});self.assertEqual(result['status']['state'],'ready')
    def test_legacy_setting_works_without_double_award(self):
        result=SeasonBonusService(PlayoffFacts()).compute(None,1,[1,2],{'farthestInPlayoffs':{'farthest':3},'playoffDepth':{'first':9}})
        self.assertEqual(result['points'],{1:3,2:0})
        result=SeasonBonusService(PlayoffFacts()).compute(None,1,[1,2],{'playoffDepth':{'first':3}})
        self.assertEqual(result['points'],{1:3,2:0})
    def test_unfinished_or_unverified_final_cannot_produce_final_award(self):
        for field,value in [('isCompleted',False),('roundOrder',None),('bonusTournamentCode',None)]:
            facts=PlayoffFacts();game=facts.playoff_games()[0];game[field]=value;facts.playoff_games=lambda *args:[game]
            result=SeasonBonusService(facts).compute(None,1,[1,2],{'farthestInPlayoffs':{'farthest':3}})
            self.assertEqual(result['points'],{1:0,2:0});self.assertEqual(result['status']['state'],'pending')
    def test_ended_phase_without_championship_result_remains_pending(self):
        facts=PlayoffFacts();game=facts.playoff_games()[0];game['roundOrder']=3;facts.playoff_games=lambda *args:[game]
        self.assertEqual(SeasonBonusService(facts).compute(None,1,[1,2],{'playoffDepth':{'first':3}})['status']['state'],'pending')

class NationalIngestionTests(unittest.TestCase):
    def test_conference_title_and_bowl_cannot_enter_national_phase_by_date(self):
        import datetime as dt
        from unittest.mock import MagicMock
        from endpoints.schedule.ingestion_service import ScheduleIngestionService
        service=ScheduleIngestionService(MagicMock(),'')
        phases=[{'id':1,'type':'RegularSeason','tournamentCode':None,'rules':{},'startDate':None,'endDate':None},
                {'id':2,'type':'NationalTournament','tournamentCode':'FBS_PLAYOFFS','rules':{},'startDate':None,'endDate':None}]
        service._get_season_phases=lambda _:phases
        service._lookup_sport_team_id=lambda sport,external:int(external)
        writes=[]
        service.ingestion_repository.upsert_game=lambda conn,params:(writes.append(params) or MagicMock(fetchone=lambda:(1,)))
        base={'externalGameId':'1','date':dt.datetime(2026,12,6,tzinfo=dt.timezone.utc),'homeEspnId':'10','awayEspnId':'11','homeScore':30,'awayScore':20,'homeName':'Home','awayName':'Away','broadcast':None,'isCompleted':True}
        for label,want in [('Big 12 Championship',1),('Rose Bowl',1),('College Football Playoff Quarterfinal at the Rose Bowl',2)]:
            service._insert_or_update_game(2,1,{**base,'tournamentLabels':[label]})
            self.assertEqual(writes[-1]['seasonPhaseId'],want)
        self.assertEqual(writes[0]['bonusTournamentCode'],None)
        self.assertEqual(writes[-1]['bonusTournamentCode'],'FBS_PLAYOFFS')
        self.assertEqual(writes[-1]['roundOrder'],2)

class CompleteBracketTests(unittest.TestCase):
    def test_a_final_alone_cannot_finalize_a_full_tournament(self):
        facts=PlayoffFacts();facts.tournaments=lambda *args:[{'id':20,'code':'FBS_PLAYOFFS','ended':True,'expectedRoundCounts':{1:4,2:4,3:2,4:1}}]
        result=SeasonBonusService(facts).compute(None,1,[1,2],{'playoffDepth':{'first':3}})
        self.assertEqual(result['status']['state'],'pending');self.assertEqual(result['points'],{1:0,2:0})

    def test_unrelated_subdivision_does_not_block_award(self):
        facts=PlayoffFacts();facts.context=lambda *args:{'sportSeasonId':1,'weekNumber':3,'subdivision':'FBS'}
        facts.tournaments=lambda *args:[{'id':20,'code':'FBS_PLAYOFFS','ended':True,'expectedRoundCounts':{4:1}}, {'id':21,'code':'FCS_PLAYOFFS','ended':False}]
        self.assertEqual(SeasonBonusService(facts).compute(None,1,[1,2],{'playoffDepth':{'first':3}})['status']['state'],'ready')

    def test_complete_bracket_with_byes_awards_full_points_to_tied_eliminated_teams(self):
        facts=PlayoffFacts()
        facts.tournaments=lambda *args:[{'id':20,'code':'FBS_PLAYOFFS','ended':True,'expectedRoundCounts':{1:4,2:4,3:2,4:1}}]
        games=[{'roundOrder':rnd,'homeTeamId':home,'awayTeamId':away,'homeScore':30,'awayScore':20,'isCompleted':True,'bonusTournamentCode':'FBS_PLAYOFFS'}
               for rnd,home,away in [(1,5,12),(1,6,11),(1,7,10),(1,8,9),(2,1,8),(2,4,5),(2,2,7),(2,3,6),(3,1,4),(3,2,3),(4,1,2)]]
        facts.playoff_games=lambda *args:games
        result=SeasonBonusService(facts).compute(None,1,[1,2],{'playoffDepth':{'first':3}})
        self.assertEqual(result['status']['state'],'ready');self.assertEqual(result['points'],{1:3,2:3})
        games[8]['awayTeamId']=12 # a first-round loser cannot reappear in a semifinal
        self.assertEqual(SeasonBonusService(facts).compute(None,1,[1,2],{'playoffDepth':{'first':3}})['status']['state'],'pending')
