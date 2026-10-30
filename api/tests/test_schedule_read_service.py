"""Read policy/projection contracts from supplied SQL facts; native SQL checked separately."""
import copy
import datetime as dt
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from rules.leagueRules import resolve_rules
from endpoints.schedule.scheduleModel import ScheduleModel


class ReadEngine:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []
        self.outcomes = []
        self.failure = None

    @contextmanager
    def begin(self):
        try:
            yield self
        except Exception:
            self.outcomes.append('rollback')
            raise
        else:
            self.outcomes.append('commit')

    def execute(self, statement, params):
        self.calls.append((str(statement), params))
        if self.failure:
            raise self.failure
        rows = [SimpleNamespace(_mapping=row) for row in self.rows]
        return SimpleNamespace(fetchall=lambda: rows, fetchone=lambda: rows[0] if rows else None)


class ScheduleReadServiceTests(unittest.TestCase):
    def service(self, rows, settings=None):
        from endpoints.schedule.read_service import ScheduleReadService
        engine = ReadEngine(rows)
        service = ScheduleReadService(engine)
        service._get_league = lambda league_id: {'sport':1,'settings':settings or {}}
        return service, engine

    def game(self, **overrides):
        game = dict(id=1,rawMemberPointDiff=21,ownsHome=True,ownsAway=False,
                    homeTeamTier=1,awayTeamTier=3,phaseRules={})
        game.update(overrides)
        return game

    def test_member_perspectives_double_owned_and_source_facts_unchanged(self):
        facts = [self.game(), self.game(ownsHome=False,ownsAway=True),
                 self.game(ownsAway=True,rawMemberPointDiff=0)]
        before = copy.deepcopy(facts)
        service, engine = self.service(facts)
        games = service.member_games_for_job(10,11,2)
        self.assertEqual([game['memberPointDiff'] for game in games],[11,42,0])
        self.assertFalse(games[2]['tierAdjustment']['applied'])
        self.assertEqual(facts,before)
        self.assertEqual((len(engine.calls),engine.outcomes),(1,['commit']))

    def test_phase_positive_only_multiplier_and_non_owned_guard(self):
        phase = {'positiveOnly':True,'marginMultiplier':3}
        service, _ = self.service([self.game(phaseRules=phase),
            self.game(rawMemberPointDiff=-21,phaseRules=phase),self.game(ownsHome=False)])
        games = service.member_games_for_job(10,11,2)
        self.assertEqual([game['memberPointDiff'] for game in games],[33,0,0])
        self.assertEqual(games[0]['tournamentAdjustment'],
                         {'positiveOnly':True,'multiplier':3,'scoringMargin':33})

    def test_invalid_rules_fail_before_game_query_even_for_empty_result(self):
        service, engine = self.service([],{'ruleSetVersion':'unknown'})
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            service.member_games_for_job(10,11,2)
        self.assertEqual(engine.calls,[])

    def test_supplied_rules_bypass_league_lookup(self):
        service, engine = self.service([self.game()])
        def unexpected(_): raise AssertionError('Supplied rules should avoid lookup')
        service._get_league = unexpected
        self.assertEqual(service.member_games_for_job(10,11,2,resolve_rules(1,{}))[0]['memberPointDiff'],11)
        self.assertEqual(len(engine.calls),1)

    def test_head_to_head_week_and_owned_projections_and_missing_week(self):
        stamp = dt.datetime(2026,11,3,tzinfo=dt.timezone.utc)
        facts = [{'id':7,'date':stamp,'homeOwnedByA':True,'awayOwnedByB':True}]
        service, _ = self.service(facts)
        self.assertEqual(service.head_to_head_for_job(10,11,12,2),facts)
        self.assertEqual(service.week_for_job(10,2),facts[0])
        self.assertEqual(service.owned_teams_for_job(10,11,2),facts)
        empty, _ = self.service([])
        self.assertIsNone(empty.week_for_job(10,99))
        self.assertEqual(empty.head_to_head_for_job(10,11,12,99),[])
        self.assertEqual(empty.owned_teams_for_job(10,11,99),[])

    def test_query_failure_propagates_and_unwinds_scope(self):
        service, engine = self.service([])
        engine.failure = RuntimeError('synthetic read failure')
        with self.assertRaisesRegex(RuntimeError,'synthetic read'):
            service.member_games_for_job(10,11,2)
        self.assertEqual(engine.outcomes,['rollback'])

    def test_legacy_db_only_inheritance_and_helper_override(self):
        from endpoints.schedule.read_service import ScheduleReadService
        self.assertTrue(issubclass(ScheduleModel,ScheduleReadService))
        class CustomModel(ScheduleModel):
            def _get_league(self, league_id): return {'sport':1,'settings':{'ruleSetVersion':'bad'}}
        model = CustomModel.__new__(CustomModel)
        with self.assertRaisesRegex(ValueError,'Unsupported'):
            model.get_member_games_for_week(10,11,2)
        legacy = ScheduleModel.__new__(ScheduleModel)
        legacy.db = ReadEngine([])
        self.assertIsNone(legacy.get_week_for_league(10,99))
