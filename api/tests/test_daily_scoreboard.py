import datetime as dt
import unittest
from unittest.mock import MagicMock
from actors import UserActor
from endpoints.roster.contracts import RosterAccessDenied
from endpoints.schedule.daily_scoreboard import daily_bounds, DailyScoreboardService


class DailyScoreboardTests(unittest.TestCase):
    def test_calendar_day_uses_league_timezone_and_dst_not_24_hour_assumption(self):
        start, end = daily_bounds('2027-03-14', 'America/Chicago')
        self.assertEqual(start, dt.datetime(2027, 3, 14, 6, tzinfo=dt.timezone.utc))
        self.assertEqual(end, dt.datetime(2027, 3, 15, 5, tzinfo=dt.timezone.utc))
        self.assertEqual((end-start).total_seconds(), 23*3600)
        for invalid in ('20270213', '2027-02-30', 'not-a-date', None):
            with self.assertRaises(ValueError): daily_bounds(invalid, 'UTC')

    def test_all_games_returned_without_owned_team_or_conference_filter(self):
        engine, repository = MagicMock(), MagicMock()
        repository.league.return_value = dict(sport=1, sportSeasonId=37, seasonYear=2026,
                                             settings={'timezone': 'America/Chicago'})
        games = [dict(id=1, homeOwnerMemberId=None), dict(id=2, homeOwnerMemberId=12)]
        repository.games.return_value = games
        service = DailyScoreboardService(engine, repository)
        result = service.read(UserActor(1, 'subject'), 10, '2027-02-13')
        self.assertEqual(result['games'], games)
        self.assertEqual(result['timezone'], 'America/Chicago')
        self.assertEqual(result['date'], '2027-02-13')
        params = repository.games.call_args.args[1]
        self.assertEqual(params['leagueId'], 10)
        self.assertEqual(params['sportSeasonId'], 37)
        self.assertEqual(params['dayStart'].hour, 6)

    def test_verified_actor_and_access_required_and_revocation_prevents_publication(self):
        engine, repository = MagicMock(), MagicMock()
        service = DailyScoreboardService(engine, repository)
        with self.assertRaises(TypeError): service.read(None, 10, '2027-02-13')
        engine.connect.assert_not_called()
        repository.league.return_value = None
        with self.assertRaises(RosterAccessDenied): service.read(UserActor(1, 'subject'), 10, '2027-02-13')
        repository.games.assert_not_called()
        repository.league.side_effect = [dict(sport=1, seasonYear=2026, sportSeasonId=37, settings={}), None]
        with self.assertRaises(RosterAccessDenied): service.read(UserActor(1, 'subject'), 10, '2027-02-13')
