"""Real allocation/advance SQL for optional conferences and exhausted owners."""
import json
import unittest
from sqlalchemy import text
from endpoints.draft.pick_service import DraftPickService
from endpoints.draft.snapshot_service import DraftSnapshotService
import test_draft_control_authorization as fixture


class DraftExhaustionTests(unittest.TestCase):
    def setUp(self):
        base = fixture.DraftControlAuthorizationTests(); base.setUp()
        self.addCleanup(base.doCleanups)
        self.db = base.db
        self.service = DraftPickService(self.db)
        self.db.connection.executescript('''
            DELETE FROM "DraftPick"; DELETE FROM "DraftTurn"; DELETE FROM "DraftState";
            DELETE FROM "ConferenceMembership"; DELETE FROM "SportTeam";
            DELETE FROM "SportConference"; DELETE FROM "Conference";
            UPDATE "League" SET "numPlayers"=3,status='Drafting' WHERE id=10;
            INSERT INTO "LeagueMember" VALUES (13,10,3,'Third Owner',3);
            INSERT INTO "Conference" VALUES (401,'A'),(402,'B'),(403,'C');
            INSERT INTO "SportConference" VALUES (501,1,401,1),(502,1,402,1),(503,1,403,1);
            INSERT INTO "SportTeam" VALUES (101,1,'A1'),(102,1,'A2'),(103,1,'A3'),(201,1,'B1'),(202,1,'B2'),(301,1,'C1');
            INSERT INTO "ConferenceMembership" VALUES (101,1,2026,501),(102,1,2026,501),(103,1,2026,501),
                (201,1,2026,502),(202,1,2026,502),(301,1,2026,503);
            INSERT INTO "DraftTurn" VALUES (10,1,11),(10,2,12),(10,3,13),(10,4,13),(10,5,12),(10,6,11);
            INSERT INTO "DraftState" ("leagueId",status,"currentOverallPickNumber","currentMemberId") VALUES (10,'live',1,11);
        ''')
        self.db.connection.commit()

    def pick(self, member, team):
        self.db.connection.execute('UPDATE "DraftState" SET "expiresAt"=NULL WHERE "leagueId"=10')
        return self.service.pick_live_for_job(10, member, team)

    def first_four(self):
        self.pick(11,101); self.pick(12,201); self.pick(13,202)
        return self.pick(13,301)

    def snapshot(self):
        return DraftSnapshotService(self.db).snapshot_for_job(10)

    def test_scarce_pick_allowed_and_last_stuck_owner_skipped(self):
        result = self.first_four()  # C1 is legal even though it strands owner 11.
        self.assertFalse(result['draftComplete'])
        self.assertEqual(result['nextMemberId'],12)
        self.assertIsNone(self.snapshot()['onDeck'])
        result = self.pick(12,102)
        self.assertTrue(result['draftComplete'])
        state = self.snapshot()['state']
        self.assertEqual(state['status'],'complete')
        self.assertIsNone(state['currentMemberId']); self.assertIsNone(state['expiresAt'])
        counts = dict(self.db.connection.execute('SELECT "memberId",COUNT(*) FROM "LeagueTeamSlot" WHERE "leagueId"=10 GROUP BY "memberId"'))
        self.assertEqual(counts,{11:1,12:2,13:2})
        self.assertEqual(self.db.connection.execute('SELECT COUNT(*) FROM "DraftPick" WHERE "leagueId"=10').fetchone()[0],5)

    def test_stuck_owner_in_middle_skipped_without_changing_other_turns(self):
        self.db.connection.executescript('''
            INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia")
                VALUES (10,12,101,1,'Prior'),(10,12,201,1,'Prior'),(10,12,301,1,'Prior');
        ''')
        result = self.pick(11,102)
        self.assertEqual((result['nextOverallPickNumber'],result['nextMemberId']),(3,13))
        self.assertEqual(self.db.connection.execute('SELECT "memberId" FROM "DraftTurn" WHERE "leagueId"=10 AND "overallPickNumber"=2').fetchone()[0],12)

    def test_timeout_skips_stuck_current_owner_before_expiry_for_both_modes(self):
        for mode in ('AUTO-SKIP','AUTO-PICK'):
            with self.subTest(mode=mode):
                settings = {'draft':{'draftType':'SNAKE','selectionTime':60,'numberOfRounds':2,'timeoutAction':mode}}
                self.db.connection.execute('UPDATE "League" SET settings=? WHERE id=10',(json.dumps(settings),))
                self.db.connection.execute('UPDATE "DraftState" SET "currentOverallPickNumber"=1,"currentMemberId"=11,"expiresAt"=NULL WHERE "leagueId"=10')
                self.db.connection.execute('DELETE FROM "LeagueTeamSlot"')
                self.db.connection.executescript('''
                    INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia")
                        VALUES (10,11,101,1,'Prior'),(10,11,201,1,'Prior'),(10,11,301,1,'Prior');
                ''')
                result = self.service.process_timeout_for_job(10)
                self.assertIsNotNone(result)
                self.assertEqual((result['nextOverallPickNumber'],result['nextMemberId']),(2,12))
                self.assertEqual(self.db.connection.execute('SELECT COUNT(*) FROM "DraftPick"').fetchone()[0],0)

    def test_all_remaining_stuck_finishes_without_allocations(self):
        self.first_four()
        self.db.connection.execute('DELETE FROM "ConferenceMembership" WHERE "sportTeamId" IN (102,103)')
        self.db.connection.commit()
        result = self.service.process_timeout_for_job(10)
        self.assertIsNotNone(result)
        self.assertTrue(result['draftComplete'])
        self.assertEqual(self.snapshot()['state']['status'],'complete')
        self.assertEqual(self.db.connection.execute('SELECT COUNT(*) FROM "DraftPick"').fetchone()[0],4)

    def test_auto_pick_last_legal_turn_completes(self):
        self.first_four()
        settings = {'draft':{'draftType':'SNAKE','selectionTime':60,'numberOfRounds':2,'timeoutAction':'AUTO-PICK'}}
        self.db.connection.execute('UPDATE "League" SET settings=? WHERE id=10',(json.dumps(settings),))
        self.db.connection.execute('UPDATE "DraftState" SET "expiresAt"=? WHERE "leagueId"=10',('2000-01-01T00:00:00+00:00',))
        self.db.connection.commit()
        self.service.pick_repository.timeout_expired = lambda conn,params: conn.execute(text('SELECT 1 AS "isExpired"'),{})
        result = self.service.process_timeout_for_job(10)
        self.assertTrue(result['draftComplete'])
        self.assertEqual(self.snapshot()['state']['status'],'complete')

    def test_expired_auto_skip_rotates_eligible_owner_and_bypasses_stuck_owner(self):
        self.db.connection.executescript('''
            INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia")
                VALUES (10,12,101,1,'Prior'),(10,12,201,1,'Prior'),(10,12,301,1,'Prior');
            UPDATE "DraftState" SET "expiresAt"='2000-01-01T00:00:00+00:00' WHERE "leagueId"=10;
        ''')
        self.service.pick_repository.timeout_expired = lambda conn,params: conn.execute(text('SELECT 1 AS "isExpired"'),{})
        result = self.service.process_timeout_for_job(10)
        self.assertEqual(result['type'],'AUTO-SKIP-MOVE-TO-END')
        self.assertEqual((result['nextOverallPickNumber'],result['nextMemberId']),(2,13))
        turns = [row[0] for row in self.db.connection.execute('SELECT "memberId" FROM "DraftTurn" WHERE "leagueId"=10 ORDER BY "overallPickNumber"')]
        self.assertEqual(turns,[12,13,13,12,11,11])
        self.assertEqual(self.db.connection.execute('SELECT COUNT(*) FROM "DraftPick"').fetchone()[0],0)

    def test_worker_schedules_stuck_null_clock_without_waiting(self):
        from worker.draftTimeoutWorker import _get_next_expired_or_soonest_deadline
        self.first_four()
        self.db.connection.execute('DELETE FROM "ConferenceMembership" WHERE "sportTeamId" IN (102,103)')
        self.db.connection.execute('UPDATE "DraftState" SET "expiresAt"=NULL WHERE "leagueId"=10')
        self.db.connection.commit()
        from unittest.mock import patch
        # Adapt only the existing PostgreSQL interval query to SQLite. The
        # fixture has no running clocks, so its equivalent query returns none.
        def deadlines(repository, conn):
            return conn.execute(text('''SELECT "leagueId", 0 AS "secondsUntilDeadline" FROM "DraftState"
                WHERE status='live' AND "expiresAt" IS NOT NULL LIMIT 1'''), {})
        with patch('endpoints.draft.pick_repository.DraftPickRepository.next_timeout_deadline', deadlines):
            with self.db.begin() as conn:
                self.assertEqual(_get_next_expired_or_soonest_deadline(conn),(10,0.0))
        result = self.service.process_timeout_for_job(10)
        self.assertTrue(result['draftComplete'])

    def test_paused_stuck_draft_is_unchanged(self):
        self.db.connection.execute('UPDATE "DraftState" SET status=\'paused\' WHERE "leagueId"=10')
        self.db.connection.commit()
        before = self.snapshot()
        self.assertIsNone(self.service.process_timeout_for_job(10))
        after = self.snapshot()
        self.assertEqual(before['state'],after['state'])
