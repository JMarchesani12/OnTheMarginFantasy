import datetime as dt
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from endpoints.schedule.helpers.espn.espnClient import ESPNClient

class KickoffTests(unittest.TestCase):
    def event(self, valid, date='2026-10-31T04:00Z'):
        return {'id': '1', 'date': date, 'competitions': [{
            'timeValid': valid, 'competitors': [
                {'homeAway': 'home', 'team': {'id': '1'}},
                {'homeAway': 'away', 'team': {'id': '2'}}]}]}

    def test_unknown_kickoff_preserves_saturday_in_chicago(self):
        from zoneinfo import ZoneInfo
        game = ESPNClient('', '').extract_game_from_event(self.event(False))
        self.assertTrue(game['timeTBD'])
        self.assertEqual(game['date'].astimezone(ZoneInfo('America/Chicago')).date(), dt.date(2026, 10, 31))

    def test_confirmed_late_game_keeps_actual_instant(self):
        game = ESPNClient('', '').extract_game_from_event(self.event(True))
        self.assertFalse(game['timeTBD'])
        self.assertEqual(game['date'], dt.datetime(2026, 10, 31, 4, tzinfo=dt.timezone.utc))

    def test_missing_flag_does_not_guess_from_clock(self):
        event = self.event(True)
        del event['competitions'][0]['timeValid']
        self.assertFalse(ESPNClient('', '').extract_game_from_event(event)['timeTBD'])
