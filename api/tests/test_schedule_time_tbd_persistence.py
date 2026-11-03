"""Merged kickoff flags must survive canonical persistence and projection."""
import datetime as dt
import sqlite3
import unittest
from unittest.mock import MagicMock
from endpoints.schedule.ingestion_repository import ScheduleIngestionRepository
from endpoints.schedule.ingestion_service import ScheduleIngestionService
from endpoints.schedule.read_repository import ScheduleReadRepository


class Connection:
    def __init__(self, raw):
        self.raw = raw
    def execute(self, statement, params):
        return self.raw.execute(str(statement), params)


class KickoffPersistenceTests(unittest.TestCase):
    def test_insert_and_reannouncement_update_preserve_flag_and_identity(self):
        raw = sqlite3.connect(':memory:')
        self.addCleanup(raw.close)
        raw.executescript('''CREATE TABLE GameResult (
            id INTEGER PRIMARY KEY, sport INTEGER, sportSeasonId INTEGER,
            seasonPhaseId INTEGER, externalGameId TEXT, date TEXT, timeTBD BOOLEAN NOT NULL DEFAULT false,
            homeTeamId INTEGER, awayTeamId INTEGER, homeScore INTEGER, awayScore INTEGER,
            homeTeamExternalId TEXT, awayTeamExternalId TEXT, homeTeamName TEXT, awayTeamName TEXT,
            broadcast TEXT, UNIQUE(sport,sportSeasonId,externalGameId));''')
        params = dict(sport=1,sportSeasonId=2,seasonPhaseId=None,externalGameId='synthetic',
            date='2026-11-02T17:00:00Z',timeTBD=True,homeTeamId=11,awayTeamId=12,
            homeScore=None,awayScore=None,homeTeamExternalId='11',awayTeamExternalId='12',
            homeTeamName='Home',awayTeamName='Away',broadcast=None)
        repository = ScheduleIngestionRepository()
        first = repository.upsert_game(Connection(raw), params).fetchone()[0]
        self.assertEqual(raw.execute('SELECT timeTBD FROM GameResult').fetchone()[0], 1)
        params.update(timeTBD=False,date='2026-11-03T02:00:00Z')
        second = repository.upsert_game(Connection(raw), params).fetchone()[0]
        self.assertEqual(first, second)
        self.assertEqual(raw.execute('SELECT timeTBD,date FROM GameResult').fetchall(), [(0,params['date'])])

    def test_service_passes_true_and_missing_false_to_repository(self):
        engine, repository = MagicMock(), MagicMock()
        service = ScheduleIngestionService(engine, '', repository=repository)
        service._lookup_sport_team_id = lambda *_: 11
        service._lookup_season_phase_id_for_game = lambda *_, **__: None
        game = dict(externalGameId='synthetic',date=dt.datetime(2026,11,2,tzinfo=dt.timezone.utc),
            homeEspnId='11',awayEspnId='12',homeScore=None,awayScore=None,
            homeName='Home',awayName='Away',broadcast=None)
        for flag in (True, None):
            if flag is not None: game['timeTBD'] = flag
            else: game.pop('timeTBD', None)
            service._insert_or_update_game(1,2,game)
            self.assertIs(repository.upsert_game.call_args.args[1]['timeTBD'], flag is True)

    def test_all_game_read_projections_include_kickoff_flag(self):
        repository = ScheduleReadRepository()
        for name in ('member_games','head_to_head_games','conference_games','team_season_games'):
            with self.subTest(projection=name):
                conn = MagicMock()
                getattr(repository, name)(conn, {})
                self.assertIn('gr."timeTBD"', str(conn.execute.call_args.args[0]))
