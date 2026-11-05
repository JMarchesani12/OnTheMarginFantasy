"""One effective conference per team/year, including invalid/missing mappings."""
import unittest
from test_league_read_authorization import ReadDatabase


class SeasonalMembershipTests(unittest.TestCase):
    def setUp(self):
        self.db=ReadDatabase();self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            CREATE TABLE SportTeam(id INTEGER,sportId INTEGER);
            CREATE TABLE SportConference(id INTEGER,sportId INTEGER);
            CREATE TABLE ConferenceMembership(sportTeamId INTEGER,sportId INTEGER,sportConferenceId INTEGER,seasonYear INTEGER);
            INSERT INTO SportTeam VALUES (1,1),(2,1),(3,1),(4,1),(5,1),(6,1),(7,1),(8,1);
            INSERT INTO SportConference VALUES (10,1),(20,1),(30,2);
            INSERT INTO ConferenceMembership VALUES
              (1,1,10,NULL),(2,1,20,2026),(3,1,10,NULL),(3,1,20,2026),
              (4,1,10,2025),(6,1,10,NULL),(6,1,30,2026),(7,1,10,NULL),(7,1,10,2026),(8,1,10,NULL),(8,2,30,2026);
        ''')

    def test_selection_season_first_current_fallback_and_invalid_season_suppresses_default(self):
        from utils.conference_membership import conference_sql
        rows=self.db.execute(conference_sql('SELECT cm."sportTeamId",cm."sportConferenceId" FROM "ConferenceMembership" cm ORDER BY cm."sportTeamId"', ':year'),{'year':2026}).fetchall()
        self.assertEqual([tuple(r._mapping.values()) for r in rows],[(1,10),(2,20),(3,20),(7,10)])

    def test_other_year_cannot_override_default(self):
        from utils.conference_membership import conference_sql
        rows=self.db.execute(conference_sql('SELECT cm."sportTeamId",cm."sportConferenceId" FROM "ConferenceMembership" cm ORDER BY cm."sportTeamId"', ':year'),{'year':2025}).fetchall()
        self.assertEqual([tuple(r._mapping.values()) for r in rows],[(1,10),(3,10),(4,10),(6,10),(7,10),(8,10)])

class SeasonalReadConsumerTests(unittest.TestCase):
    def test_roster_and_search_return_one_seasonal_conference_and_keep_unmapped_team(self):
        import test_roster_read_authorization as fixture_module
        from endpoints.roster.repository import RosterRepository
        from endpoints.schedule.read_repository import ScheduleReadRepository
        base=fixture_module.RosterReadTests();base.setUp();self.addCleanup(base.doCleanups)
        db=base.db
        db.connection.executescript('''ALTER TABLE LeagueMember ADD COLUMN teamName TEXT DEFAULT 'Test';
            INSERT INTO SportConference VALUES (1,1,1),(2,1,2);
            INSERT INTO Conference VALUES (1,'Default'),(2,'Seasonal');
            INSERT INTO ConferenceMembership VALUES (101,1,NULL,1),(101,1,2026,2);''')
        roster=RosterRepository().member_teams(db,10,12,1)
        self.assertEqual(len(roster),1);self.assertEqual(roster[0]['conferenceName'],'Seasonal')
        rows=ScheduleReadRepository().search_teams(db,dict(sport=1,seasonYear=2026,leagueId=10,weekNumber=1)).fetchall()
        self.assertEqual([r._mapping['conferenceName'] for r in rows],['Seasonal'])
        db.connection.executescript('DELETE FROM ConferenceMembership;')
        self.assertEqual(RosterRepository().member_teams(db,10,12,1)[0]['conferenceName'],None)

class UnmappedAllocationTests(unittest.TestCase):
    def test_manual_and_live_picks_reject_unmapped_teams_atomically(self):
        import test_live_pick_authorization as fixture
        from endpoints.draft.pick_service import DraftPickService
        from actors import UserActor
        base=fixture.LivePickAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        base.db.connection.create_function('pg_notify',2,lambda *args:None)
        base.db.connection.executescript('DELETE FROM ConferenceMembership WHERE sportTeamId=102;')
        service=DraftPickService(base.db);before=base.state()
        for call in (lambda:service.allocate_manual_for_job(10,12,102),lambda:service.pick_live(UserActor(2,'bob'),10,12,102)):
            with self.assertRaises(ValueError):call()
            self.assertEqual(base.state(),before)

    def test_trade_cannot_use_missing_mapping_as_uncapped(self):
        import test_trade_application_guards as fixture
        base=fixture.TradeApplicationGuardTests();base.setUp();self.addCleanup(base.doCleanups)
        base.db.connection.executescript('DELETE FROM ConferenceMembership WHERE sportTeamId=102;')
        before=base.base.state()
        with self.assertRaises(ValueError):base.model.apply_trade(1)
        self.assertEqual(base.base.state(),before)

    def test_auto_pick_only_uses_mapped_conference_buckets(self):
        import test_live_pick_authorization as fixture
        from endpoints.draft.pick_service import DraftPickService
        base=fixture.LivePickAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        service=DraftPickService(base.db)
        with base.db.begin() as conn:self.assertEqual(service._choose_random_team_for_auto_pick(conn,10,12,1),102)
        base.db.connection.executescript('DELETE FROM ConferenceMembership WHERE sportTeamId=102;')
        with base.db.begin() as conn:self.assertIsNone(service._choose_random_team_for_auto_pick(conn,10,12,1))

class ReviewRegressionTests(unittest.TestCase):
    def test_timeout_auto_pick_rejects_unmapped_retained_roster_without_advancing(self):
        from sqlalchemy import text
        import test_live_pick_authorization as fixture
        from endpoints.draft.pick_service import DraftPickService
        base=fixture.LivePickAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        base.db.connection.create_function('pg_notify',2,lambda *args:None)
        base.db.connection.executescript('''
            INSERT INTO SportTeam VALUES (103,1,'Unmapped retained');
            INSERT INTO LeagueTeamSlot (leagueId,memberId,sportTeamId,acquiredWeek,acquiredVia) VALUES (10,12,103,1,'Prior');
            UPDATE League SET settings='{"draft":{"draftType":"SNAKE","selectionTime":60,"numberOfRounds":2,"timeoutAction":"AUTO-PICK","graceSeconds":0}}' WHERE id=10;
            UPDATE DraftState SET expiresAt='2000-01-01T00:00:00+00:00' WHERE leagueId=10;
        ''')
        service=DraftPickService(base.db)
        # SQLite port substitutes only PostgreSQL interval arithmetic.
        service.pick_repository.timeout_expired=lambda conn,params:conn.execute(text('SELECT 1 AS "isExpired"'),{})
        before=base.state()
        with self.assertRaisesRegex(ValueError,'Conference configuration'):
            service.process_timeout_for_job(10)
        self.assertEqual(base.state(),before)

    def test_cross_sport_owned_and_history_rows_keep_nullable_conference_metadata(self):
        import test_live_pick_authorization as fixture
        from endpoints.roster.repository import RosterRepository
        from endpoints.schedule.read_repository import ScheduleReadRepository
        from endpoints.draft.snapshot_repository import DraftSnapshotRepository
        base=fixture.LivePickAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        base.db.connection.executescript('''
            ALTER TABLE SportTeam ADD COLUMN tier INTEGER DEFAULT 1;
            ALTER TABLE SportTeam ADD COLUMN externalId TEXT;
            INSERT INTO Conference VALUES (402,'Other sport conference');
            INSERT INTO SportConference VALUES (502,2,402,2);
            UPDATE SportTeam SET sportId=2 WHERE id=101;
            UPDATE ConferenceMembership SET sportId=2,sportConferenceId=502 WHERE sportTeamId=101;
            INSERT INTO LeagueTeamSlot (leagueId,memberId,sportTeamId,acquiredWeek,acquiredVia) VALUES (10,11,101,1,'Prior');
        ''')
        projections=[RosterRepository().member_teams(base.db,10,11,1),
            [dict(row._mapping) for row in ScheduleReadRepository().owned_teams(base.db,dict(leagueId=10,memberId=11,weekNumber=1)).fetchall()],
            DraftSnapshotRepository().snapshot_picks(base.db,10)]
        for rows in projections:
            with self.subTest(rows=rows):
                self.assertEqual(len(rows),1)
                self.assertIsNone(rows[0]['conferenceName'])
                self.assertIsNone(rows[0]['sportConferenceId'])
