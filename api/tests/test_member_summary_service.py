"""Member read projection, timezone/date totals and schedule capability boundaries."""
import datetime as dt
import unittest
from zoneinfo import ZoneInfo
from actors import UserActor
from endpoints.league.reads.service import LeagueReadService
from endpoints.league.leagueModel import LeagueModel
import test_league_read_authorization as reads
from test_transaction_service import ConnectionOwner


class MemberSummaryServiceTests(unittest.TestCase):
    def setUp(self):
        base=reads.LeagueReadAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        self.db=base.db;self.engine=ConnectionOwner(self.db);self.service=LeagueReadService(self.engine);self.calls=[]
    def timezone(self,league):
        self.assertEqual(self.engine.active,0);self.calls.append(('timezone',league));return ZoneInfo('America/Chicago')
    def games(self,**kwargs):
        self.assertEqual(self.engine.active,0);self.calls.append(('games',kwargs));return []
    def test_actor_required_before_io_or_capabilities(self):
        self.assertTrue(hasattr(self.service,'members'),'member read operation missing')
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):self.service.members(actor,10,self.timezone,self.games)
        self.assertEqual(self.engine.connects,0);self.assertEqual(self.calls,[])
    def test_no_week_projection_and_single_read_connection(self):
        self.assertTrue(hasattr(self.service,'members'),'member read operation missing')
        rows=self.service.members(UserActor(2,'bob'),10,self.timezone,self.games)
        self.assertEqual([r['id'] for r in rows],[11,12]);self.assertEqual(rows[1]['seasonPoints'],20)
        self.assertEqual(rows[1]['currentWeekPointDifferential'],0);self.assertEqual(rows[1]['dailyPointDifferentials'],[])
        self.assertEqual(set(rows[0]),{'id','createdAt','leagueId','userId','teamName','draftOrder','seasonPoints','displayName','currentWeekPointDifferential','dailyPointDifferentials'})
        self.assertEqual(self.calls,[('timezone',10)]);self.assertEqual(self.engine.connects,1)
    def test_week_zero_local_dates_naive_aware_undated_and_zero_fill(self):
        self.assertTrue(hasattr(self.service,'members'),'member read operation missing')
        self.db.connection.execute('INSERT INTO "Week" VALUES (1,10,0,?,?)',('2026-10-27T00:00:00+00:00','2026-10-29T23:59:00+00:00'));self.db.connection.commit()
        def games(**kwargs):
            self.games(**kwargs)
            if kwargs['member_id']!=12:return []
            return [{'memberPointDiff':5,'date':'2026-10-27T01:00:00+00:00'},
                    {'memberPointDiff':-3,'date':'2026-10-28T02:00:00'},
                    {'memberPointDiff':4,'date':dt.datetime(2026,10,28,12,tzinfo=dt.timezone.utc)},
                    {'memberPointDiff':2,'date':None},{'memberPointDiff':7,'date':'2026-11-01T00:00:00Z'}]
        row=self.service.members(UserActor(2,'bob'),10,self.timezone,games)[1]
        self.assertEqual(row['currentWeekPointDifferential'],15)
        self.assertEqual(row['dailyPointDifferentials'],[{'date':'2026-10-26','pointDifferential':5},
            {'date':'2026-10-27','pointDifferential':-3},{'date':'2026-10-28','pointDifferential':4},{'date':'2026-10-29','pointDifferential':0}])
        self.assertEqual(self.calls[2],('games',{'league_id':10,'member_id':12,'week_number':0}))
    def test_denied_empty_still_resolves_timezone_without_game_calls(self):
        self.assertTrue(hasattr(self.service,'members'),'member read operation missing')
        self.assertEqual(self.service.members(UserActor(3,'outsider'),10,self.timezone,self.games),[])
        self.assertEqual(self.calls,[('timezone',10)])
    def test_timezone_error_propagates_after_read(self):
        self.assertTrue(hasattr(self.service,'members'),'member read operation missing')
        def fail(league):raise ValueError('synthetic timezone failure')
        with self.assertRaises(ValueError):self.service.members(UserActor(1,'alice'),10,fail,self.games)
        self.assertEqual(self.engine.active,0);self.assertEqual(self.engine.connects,1)
    def test_db_only_legacy_optional_reader_and_callbacks(self):
        model=LeagueModel.__new__(LeagueModel);model.db=self.engine
        class Schedule:
            _get_league_timezone=staticmethod(self.timezone)
            get_member_games_for_week=staticmethod(self.games)
        model.scheduleModel=Schedule()
        self.assertEqual(len(model.get_members_for_league(10)),2)
        self.assertEqual(model.get_members_for_league(10,reader_user_id=3),[])
