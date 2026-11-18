"""Actual shared coordinator/parser with synthetic transport and write boundary."""
import datetime as dt
from copy import deepcopy
from unittest.mock import MagicMock
import unittest
from endpoints.schedule.ingestion_service import ScheduleIngestionService
from endpoints.schedule.helpers.espn.espnClient import ESPNClient
from operations import GateLost

DAY=dt.date(2026,11,16)
def event(key='A',score=80,labels=None):
    return dict(id=key,date='2026-11-16T18:00:00Z',season={'type':2},notes=[dict(headline=x) for x in labels or []],competitions=[dict(competitors=[dict(homeAway='home',team=dict(id='1',displayName='Home'),score=str(score)),dict(homeAway='away',team=dict(id='2',displayName='Away'),score='70')])])

class SharedIngestionTests(unittest.TestCase):
    def fixture(self,groups=None,check=None):
        from endpoints.schedule.shared_ingestion_service import SharedScoreboardIngestionService
        fetches=[];writes=[];payloads={10:[event('A'),event('B'),{'id':'bad'}],20:[event('A'),event('C')]};state={'fail_once':False}
        class Client(ESPNClient):
            def fetch_scoreboard_for_date(self,datestr,group_id):
                fetches.append((self.api_keyword,datestr,group_id))
                if state['fail_once'] and group_id==20:state['fail_once']=False;raise OSError('private failure')
                return dict(events=deepcopy(payloads[group_id]))
        service=ScheduleIngestionService(MagicMock(),'https://synthetic.invalid',client_factory=Client)
        service._get_league=lambda league:dict(sport=2 if league==30 else 1)
        service._get_sport_season_for_league=lambda league:dict(sportSeasonId=3000 if league==30 else 2027 if league==20 else 2026,sportId=2 if league==30 else 1)
        service._get_sport_api_config=MagicMock(side_effect=lambda sport:('sport-'+str(sport),groups if groups is not None else [10,20],'ignored'))
        service._insert_or_update_game=lambda sport,season,game:writes.append((sport,season,deepcopy(game)))
        coordinator=SharedScoreboardIngestionService(service,check or (lambda:None))
        return coordinator,service,fetches,writes,payloads,state

    def test_same_season_leagues_share_raw_summary_and_work(self):
        c,s,fetches,writes,payloads,state=self.fixture();out=list(c.iter_league_outcomes(range(1,17),DAY))
        self.assertEqual(len(fetches),2);self.assertEqual([w[2]['externalGameId'] for w in writes],['A','B','C'])
        self.assertEqual([r['leagueId'] for r in out],list(range(1,17)))
        self.assertTrue(all(r['summary']['eventsSeen']==5 and r['error'] is None for r in out));s._get_sport_api_config.assert_called_once_with(1)
        out[0]['summary']['eventsSeen']=999;self.assertEqual(out[1]['summary']['eventsSeen'],5)

    def test_later_revision_and_reversion_and_phase_only_change(self):
        for mode in ('revision','reversion','phase'):
            c,s,fetches,writes,payloads,state=self.fixture([10,20,30])
            payloads[10]=[event('A')];payloads[20]=[event('A',90, ['Final'] if mode=='phase' else [])];payloads[30]=[event('A') if mode=='reversion' else deepcopy(payloads[20][0])]
            if mode=='phase':payloads[20][0]=event('A',80,['Final']);payloads[30]=deepcopy(payloads[20])
            list(c.iter_league_outcomes([1,2],DAY))
            self.assertEqual(len(writes),3 if mode=='reversion' else 2)
            self.assertEqual(writes[-1][2]['homeScore'],80 if mode in ('reversion','phase') else 90)
            if mode=='phase':self.assertEqual(writes[-1][2]['tournamentLabels'],['Final'])

    def test_shared_failure_fans_out_other_season_continues_and_new_run_refetches(self):
        c,s,fetches,writes,payloads,state=self.fixture();state['fail_once']=True
        out=list(c.iter_league_outcomes([1,20,2],DAY))
        self.assertEqual([r['leagueId'] for r in out],[1,20,2]);self.assertEqual([r['error'] is not None for r in out],[True,False,True]);self.assertEqual(len(fetches),4)
        self.assertEqual([w[2]['externalGameId'] for w in writes if w[1]==2026],['A','B'])
        from endpoints.schedule.shared_ingestion_service import SharedScoreboardIngestionService
        retry=list(SharedScoreboardIngestionService(s,lambda:None).iter_league_outcomes([1,2],DAY));self.assertTrue(all(r['error'] is None for r in retry));self.assertEqual(len(fetches),6)

    def test_metadata_date_sport_and_duplicate_group_isolation(self):
        c,s,fetches,writes,payloads,state=self.fixture([10,10,20]);original=s._get_league
        s._get_league=lambda league:(_ for _ in ()).throw(ValueError('missing')) if league==99 else original(league)
        out=list(c.iter_league_outcomes([99,1,20,30,2],DAY));self.assertIsInstance(out[0]['error'],ValueError);self.assertEqual(len(fetches),6)
        list(c.iter_league_outcomes([1],DAY+dt.timedelta(days=1)));self.assertEqual(len(fetches),8)
        self.assertEqual([x[2] for x in fetches],[10,20]*4)
        self.assertEqual(out[1]['summary']['eventsSeen'],5)
        c,s,fetches,writes,payloads,state=self.fixture([]);self.assertEqual(list(c.iter_league_outcomes([1],DAY))[0]['summary']['eventsSeen'],0);self.assertEqual(fetches,[])

    def test_mutable_parser_mapping_cannot_change_previous_applied_copy(self):
        c,s,fetches,writes,payloads,state=self.fixture([10]);shared={'externalGameId':'A','homeScore':80,'tournamentLabels':[]}
        class Client:
            def fetch_scoreboard_for_date(self,*a):return None
            def iter_scoreboard_events(self,payload):return iter([80,90,80])
            def extract_game_from_event(self,value):shared['homeScore']=value;return shared
        s._new_client=lambda *a:Client();list(c.iter_league_outcomes([1],DAY))
        self.assertEqual([w[2]['homeScore'] for w in writes],[80,90,80])

    def test_write_failure_is_shared_without_false_success(self):
        c,s,fetches,writes,payloads,state=self.fixture();original=s._insert_or_update_game
        def fail(sport,season,game):
            if game['externalGameId']=='B':raise RuntimeError('commit')
            original(sport,season,game)
        s._insert_or_update_game=fail;out=list(c.iter_league_outcomes([1,2],DAY))
        self.assertTrue(all(r['summary'] is None and isinstance(r['error'],RuntimeError) for r in out));self.assertEqual(len(fetches),1);self.assertEqual(len(writes),1)

    def test_gate_loss_propagates_and_stops_all_following_boundaries(self):
        for stop in range(1,10):
            calls=[]
            def check():
                calls.append(1)
                if len(calls)==stop:raise GateLost()
            c,s,fetches,writes,payloads,state=self.fixture(check=check)
            with self.assertRaises(GateLost):list(c.iter_league_outcomes([1,2],DAY))
            self.assertEqual(len(calls),stop)
