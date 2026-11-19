"""Real-world team analytics share the league's margin rules, never roster ownership."""
import unittest
from rules.leagueRules import resolve_rules
from endpoints.roster.team_performance import summarize_team_performance


class TeamPerformanceTests(unittest.TestCase):
    def game(self, **changes):
        return dict(id=1, homeTeamId=10, awayTeamId=20, homeScore=74, awayScore=70,
                    homeTeamTier=1, awayTeamTier=3, homeTeamUnranked=False,
                    awayTeamUnranked=False, isCompleted=True, inWeek=True,
                    phaseRules={}, **changes)

    def summarize(self, games):
        return {row['teamId']: row for row in summarize_team_performance(
            [10, 20, 30], games, 1, resolve_rules(1, {}))}

    def test_both_sides_use_their_own_adjusted_margin_and_season_average(self):
        first = self.game()
        second = {**self.game(), 'id': 2, 'homeScore': 68, 'inWeek': False}
        result = self.summarize([first, second])
        self.assertEqual(result[10]['weekDifferential'], 2)
        self.assertEqual(result[10]['seasonDifferential'], -2)
        self.assertEqual(result[10]['averageDifferential'], -1)
        self.assertEqual(result[10]['gamesPlayed'], 2)
        self.assertEqual(result[20]['seasonDifferential'], 2)
        self.assertEqual(result[20]['averageDifferential'], 1)

    def test_live_scheduled_and_unknown_completion_never_count(self):
        games = [{**self.game(), 'id': i, 'isCompleted': state}
                 for i, state in enumerate([False, None, True])]
        result = self.summarize(games)
        self.assertEqual(result[10]['gamesPlayed'], 1)
        self.assertEqual(result[10]['weekGamesPlayed'], 1)
        self.assertEqual(result[10]['unconfirmedGames'], 1)
        self.assertIsNone(result[30]['averageDifferential'])
        self.assertEqual(result[30]['gamesPlayed'], 0)

    def test_tournament_rules_unranked_opponents_and_duplicate_games(self):
        game = {**self.game(), 'awayTeamTier': 2, 'awayTeamUnranked': True,
                'phaseRules': {'positiveOnly': True, 'marginMultiplier': 2}}
        result = self.summarize([game, game])
        self.assertEqual(result[10]['seasonDifferential'], 4)
        self.assertEqual(result[20]['seasonDifferential'], 0)
        self.assertEqual(result[10]['gamesPlayed'], 1)

class TeamPerformanceAccessTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import MagicMock
        from endpoints.roster.team_performance import TeamPerformanceService
        self.engine = MagicMock()
        self.repository = MagicMock()
        self.service = TeamPerformanceService(self.engine, self.repository)

    def test_unverified_actor_is_rejected_before_io(self):
        for actor in (None, 1, {'user_id': 1}):
            with self.assertRaises(TypeError):
                self.service.read(actor, 10, 1)
        self.engine.connect.assert_not_called()

    def test_denied_league_and_invalid_week_cannot_read_games(self):
        from actors import UserActor
        from endpoints.roster.contracts import RosterAccessDenied, RosterWeekUnavailable
        self.repository.context.return_value = None
        with self.assertRaises(RosterAccessDenied):
            self.service.read(UserActor(1, 'subject'), 10, 1)
        self.repository.context.return_value = {'weekId': None}
        with self.assertRaises(RosterWeekUnavailable):
            self.service.read(UserActor(1, 'subject'), 10, 99)
        self.repository.games.assert_not_called()

    def test_revocation_during_read_does_not_publish_stats(self):
        from actors import UserActor
        from endpoints.roster.contracts import RosterAccessDenied
        self.repository.context.side_effect = [{'weekId': 1, 'sport': 1}, None]
        self.repository.teams.return_value = [10]
        self.repository.games.return_value = []
        with self.assertRaises(RosterAccessDenied):
            self.service.read(UserActor(1, 'subject'), 10, 1)
