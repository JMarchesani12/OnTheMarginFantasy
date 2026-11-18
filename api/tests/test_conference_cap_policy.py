"""MOD-033A cap contracts on actual services and disposable SQLite fixtures.

PostgreSQL interval/lock behavior is not established by this fixture suite.
"""
import unittest
from unittest.mock import patch
from sqlalchemy import text
from actors import UserActor
from endpoints.draft.pick_service import DraftPickService
import test_live_pick_authorization as live
import test_transaction_service as transaction_fixture


class ConferenceCapValueTests(unittest.TestCase):
    def test_zero_and_positive_values_have_no_unlimited_default(self):
        from utils.conference_caps import require_conference_cap
        for value in (0, 1, 3, 1000):
            with self.subTest(value=value):
                self.assertEqual(require_conference_cap(value, 501), value)

    def test_invalid_values_are_configuration_errors_not_limits(self):
        from utils.conference_caps import require_conference_cap
        for value in (None, -1, -100, True, False, 1.5, 2.0, '3', '', {}, []):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, 'configuration.*501'):
                    require_conference_cap(value, 501)


class DraftConferenceCapTests(unittest.TestCase):
    def setUp(self):
        base = live.LivePickAuthorizationTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db, self.state = base.db, base.state
        self.engine = transaction_fixture.ConnectionOwner(self.db)
        self.service = DraftPickService(self.engine)

    def cap(self, value):
        self.db.connection.execute('UPDATE SportConference SET maxTeamsPerOwner=?', (value,))
        self.db.connection.commit()

    def test_live_and_manual_zero_cap_reject_without_picks_or_state_advance(self):
        self.cap(0)
        before = self.state()
        for call in (lambda: self.service.pick_live(UserActor(2, 'bob'), 10, 12, 102),
                     lambda: self.service.allocate_manual_for_job(10, 12, 102)):
            with self.assertRaisesRegex(ValueError, 'Conference cap reached'):
                call()
            self.assertEqual(self.state(), before)
        self.assertEqual((self.engine.begins, self.engine.connects), (2, 0))

    def test_live_and_manual_invalid_configuration_fail_without_writes(self):
        for value in (-1, None):
            self.cap(value)
            before = self.state()
            for call in (lambda: self.service.pick_live(UserActor(2, 'bob'), 10, 12, 102),
                         lambda: self.service.allocate_manual_for_job(10, 12, 102)):
                with self.assertRaisesRegex(ValueError, 'configuration'):
                    call()
                self.assertEqual(self.state(), before)

    def test_positive_limit_allows_equal_then_rejects_over_cap(self):
        self.cap(1)
        self.service.pick_live(UserActor(2, 'bob'), 10, 12, 102)
        self.db.connection.executescript('''UPDATE DraftState SET expiresAt=NULL WHERE leagueId=10;
            INSERT INTO SportTeam VALUES (103,1,'Extra');
            INSERT INTO ConferenceMembership VALUES (103,1,2026,501);''')
        before = self.state()
        with self.assertRaisesRegex(ValueError, 'Conference cap reached'):
            self.service.pick_live(UserActor(2, 'bob'), 10, 12, 103)
        self.assertEqual(self.state(), before)

    def test_end_exclusive_and_future_history_do_not_consume_positive_cap(self):
        self.cap(1)
        self.db.connection.executescript('''INSERT INTO LeagueTeamSlot
            (leagueId,memberId,sportTeamId,acquiredWeek,droppedWeek,acquiredVia)
            VALUES (10,12,101,0,1,'Draft'),(10,12,101,3,NULL,'Draft');''')
        self.service.pick_live(UserActor(2, 'bob'), 10, 12, 102, acquired_week=1)
        self.assertEqual(len(self.state()['LeagueTeamSlot']), 3)

    def test_auto_zero_bucket_skips_to_eligible_conference_and_all_zero_returns_none(self):
        self.cap(0)
        self.db.connection.execute('INSERT INTO SportConference VALUES (502,1,402,1)')
        self.db.connection.commit()
        attempted = []
        self.service._pick_random_available_team_in_conference = lambda conn, league, conference, week: attempted.append(conference) or 103
        with patch('endpoints.draft.pick_service.secrets.choice', side_effect=lambda values: values[0]):
            with self.engine.begin() as conn:
                self.assertEqual(self.service._choose_random_team_for_auto_pick(conn, 10, 12, 1), 103)
            self.assertEqual(attempted, [502])
            self.cap(0)
            with self.engine.begin() as conn:
                self.assertIsNone(self.service._choose_random_team_for_auto_pick(conn, 10, 12, 1))
            self.assertEqual(attempted, [502])

    def timeout(self):
        self.db.connection.execute('''UPDATE League SET settings=? WHERE id=10''',
            ('{"draft":{"draftType":"SNAKE","selectionTime":60,"numberOfRounds":2,"timeoutAction":"AUTO-PICK"}}',))
        self.db.connection.execute("UPDATE DraftState SET expiresAt='2000-01-01T00:00:00+00:00' WHERE leagueId=10")
        self.db.connection.commit()
        # Expiration itself is outside this policy test; all bucket reads/transaction handling are real.
        self.service.pick_repository.timeout_expired = lambda conn, params: conn.execute(text('SELECT 1 AS "isExpired"'), {})
        return self.service.process_timeout_for_job(10)

    def test_invalid_auto_cap_rolls_back_and_does_not_silently_exhaust(self):
        for value in (-1, None):
            self.cap(value)
            # Snapshot after the fixture timeout setup, before the actual operation.
            self.service.pick_repository.timeout_expired = lambda conn, params: conn.execute(text('SELECT 1 AS "isExpired"'), {})
            self.db.connection.execute('UPDATE League SET settings=? WHERE id=10',
                ('{"draft":{"selectionTime":60,"numberOfRounds":2,"timeoutAction":"AUTO-PICK"}}',))
            self.db.connection.execute("UPDATE DraftState SET expiresAt='2000-01-01T00:00:00+00:00' WHERE leagueId=10")
            self.db.connection.commit()
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'configuration'):
                self.service.process_timeout_for_job(10)
            self.assertEqual(self.state(), before)

    def test_all_zero_timeout_retains_no_team_no_advance_behavior(self):
        self.cap(0)
        before = self.state()
        self.assertIsNone(self.timeout())
        after = self.state()
        self.assertEqual(after['DraftPick'], before['DraftPick'])
        self.assertEqual(after['LeagueTeamSlot'], before['LeagueTeamSlot'])
        self.assertEqual(after['DraftState'][0]['currentOverallPickNumber'], before['DraftState'][0]['currentOverallPickNumber'])


class TransactionConferenceCapTests(unittest.TestCase):
    def setUp(self):
        import test_free_agency_authorization as free
        import test_operational_trusted_contract as operational
        from endpoints.transaction.workflow_service import TransactionWorkflowService
        base = free.FreeAgencyAuthorizationTests()
        base.database_type = operational.ApplyDatabase
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db, self.state, self.client, self.headers = base.db, base.state, base.client, base.headers
        self.db.connection.executescript('''ALTER TABLE League ADD COLUMN tradeDeadline TEXT;
            ALTER TABLE "Transaction" ADD COLUMN decidedByMemberId INTEGER;
            ALTER TABLE "Transaction" ADD COLUMN rejectReason TEXT;''')
        self.service = TransactionWorkflowService(self.db)

    def cap(self, value):
        self.db.connection.execute('UPDATE SportConference SET maxTeamsPerOwner=? WHERE id=500', (value,))
        self.db.connection.commit()

    def pending(self, kind='TRADE', status='PENDING_APPLY', drops='[101]', adds='[102]'):
        self.db.connection.execute('DELETE FROM "Transaction"')
        self.db.connection.execute('''INSERT INTO "Transaction"
            (id,leagueId,weekId,type,memberFromId,memberToId,status,fromTeamIds,toTeamIds)
            VALUES (1,10,101,?,11,?,?,?,?)''',
            (kind, 11 if kind == 'FREE_AGENT' else 12, status, drops, adds))
        self.db.connection.commit()

    def test_free_agent_submission_and_application_invalid_caps_roll_back(self):
        for cap in (-1, None):
            self.cap(cap)
            self.db.connection.execute('DELETE FROM "Transaction"')
            self.db.connection.commit()
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'configuration'):
                self.service.free_agency_add_drop(10, 100, 1, 11, 103, 101)
            self.assertEqual(self.state(), before)
            self.pending('FREE_AGENT', drops='[101]', adds='[103]')
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'configuration'):
                self.service.apply_free_agent_transaction(1)
            self.assertEqual(self.state(), before)

    def test_trade_proposal_acceptance_and_application_invalid_caps_roll_back(self):
        for cap in (-1, None):
            self.cap(cap)
            self.db.connection.execute('DELETE FROM "Transaction"')
            self.db.connection.commit()
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'configuration'):
                self.service.propose_trade(10, 100, 11, 12, [101], [102])
            self.assertEqual(self.state(), before)
            self.pending(status='PROPOSED')
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'configuration'):
                self.service.respond_to_trade(1, 'ACCEPT', 12)
            self.assertEqual(self.state(), before)
            self.pending()
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'configuration'):
                self.service.apply_trade(1)
            self.assertEqual(self.state(), before)

    def test_missing_trade_limit_does_not_default_to_999(self):
        before = self.state()
        with patch.object(self.service._transaction_service.repository, 'conference_limits', return_value={}):
            with self.assertRaisesRegex(ValueError, 'configuration'):
                self.service.propose_trade(10, 100, 11, 12, [101], [102])
        self.assertEqual(self.state(), before)

    def test_zero_blocks_free_agency_and_trade_incoming_teams_without_writes(self):
        self.cap(0)
        before = self.state()
        for call in (lambda: self.service.free_agency_add_drop(10, 100, 1, 11, 103, 101),
                     lambda: self.service.propose_trade(10, 100, 11, 12, [101], [102])):
            with self.assertRaises(ValueError):
                call()
            self.assertEqual(self.state(), before)
        for kind, adds, call in [('FREE_AGENT', '[103]', self.service.apply_free_agent_transaction),
                                 ('TRADE', '[102]', self.service.apply_trade)]:
            self.pending(kind, adds=adds)
            before = self.state()
            with self.assertRaises(ValueError):
                call(1)
            self.assertEqual(self.state(), before)

    def test_positive_equal_drop_before_add_and_zero_drop_only_keep_history(self):
        self.cap(1)
        result = self.service.free_agency_add_drop(10, 101, 99, 11, 103, 101)
        self.assertEqual((result['weekNumber'], result['status']), (2, 'PENDING_APPLY'))
        engine = transaction_fixture.ConnectionOwner(self.db)
        from endpoints.transaction.workflow_service import TransactionWorkflowService
        with engine.begin() as conn:
            TransactionWorkflowService(engine).apply_free_agent_transaction(result['transactionId'], conn=conn)
        self.assertEqual((engine.begins, engine.connects), (1, 0))
        slots = self.state()['LeagueTeamSlot']
        self.assertEqual((slots[0]['droppedWeek'], slots[-1]['acquiredWeek']), (2, 2))
        self.cap(0)
        self.db.connection.execute('DELETE FROM "Transaction"')
        self.db.connection.commit()
        result = self.service.free_agency_add_drop(10, 101, 2, 11, None, 103)
        self.assertEqual(result['memberRosterTeamIds'], [])
        self.service.apply_free_agent_transaction(result['transactionId'])
        self.assertEqual(self.state()['LeagueTeamSlot'][-1]['droppedWeek'], 2)

    def test_positive_trade_limit_and_unrelated_invalid_conference_do_not_change_contracts(self):
        self.cap(1)
        self.db.connection.execute('INSERT INTO SportConference VALUES (900,NULL,2)')
        self.db.connection.commit()
        result = self.service.propose_trade(10, 100, 11, 12, [101], [102])
        self.assertEqual(result['status'], 'PROPOSED')
        self.pending()
        engine = transaction_fixture.ConnectionOwner(self.db)
        from endpoints.transaction.service import TransactionService
        with engine.begin() as conn:
            self.assertIsNone(TransactionService(engine).apply_trade_for_job(1, conn=conn))
        self.assertEqual((engine.begins, engine.connects), (1, 0))
        self.assertEqual(self.state()['Transaction'][0]['status'], 'COMPLETED')

    def test_http_invalid_configuration_uses_existing_value_error_boundary(self):
        self.cap(None)
        response = self.client.post('/api/league/10/freeAgency/addDrop',
            json={'weekId':100,'weekNumber':1,'memberId':11,'addTeamId':103,'dropTeamId':101},
            headers=self.headers())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['error'], {'code':'request_invalid','message':'Free agency move rejected'})
        self.assertIn('configuration', response.json['details'])


class RosterCapReportingTests(unittest.TestCase):
    setUp = TransactionConferenceCapTests.setUp
    cap = TransactionConferenceCapTests.cap

    def test_zero_active_roster_is_violation_empty_roster_is_not(self):
        self.cap(0)
        violations = self.service.get_week_roster_violations(10, 100)
        self.assertEqual(sorted((v['memberId'], v['sportConferenceId'], v['count'], v['maxTeamsPerOwner']) for v in violations),
                         [(11, 500, 1, 0), (12, 500, 1, 0)])
        with self.assertRaisesRegex(ValueError, 'Roster violations'):
            self.service.assert_week_rosters_valid(10, 100)
        self.db.connection.execute('UPDATE LeagueTeamSlot SET droppedWeek=1 WHERE leagueId=10')
        self.db.connection.commit()
        self.assertEqual(self.service.get_week_roster_violations(10, 100), [])

    def test_invalid_caps_are_configuration_errors_before_violation_filtering(self):
        for value in (-1, None):
            self.cap(value)
            before = self.state()
            with self.assertRaisesRegex(ValueError, 'configuration'):
                self.service.get_week_roster_violations(10, 100)
            self.assertEqual(self.state(), before)

    def test_missing_or_invalid_season_mapping_cannot_disappear_from_report(self):
        for sql in ('DELETE FROM ConferenceMembership WHERE sportTeamId=101',
                    'INSERT INTO ConferenceMembership VALUES (101,999,1,2026)',
                    'UPDATE SportTeam SET sportId=2 WHERE id=101'):
            with self.subTest(sql=sql):
                self.db.connection.execute(sql)
                self.db.connection.commit()
                with self.assertRaisesRegex(ValueError, 'configuration'):
                    self.service.get_week_roster_violations(10, 100)
                self.db.connection.executescript('''UPDATE SportTeam SET sportId=1 WHERE id=101;
                    DELETE FROM ConferenceMembership WHERE sportTeamId=101;
                    INSERT INTO ConferenceMembership VALUES (101,500,1,NULL);''')

    def test_positive_counts_keep_shape_history_and_unrelated_config_is_ignored(self):
        self.cap(1)
        self.db.connection.executescript('''INSERT INTO SportConference VALUES (900,NULL,2);
            INSERT INTO LeagueTeamSlot VALUES (4,10,11,103,2,NULL,'Draft');
            INSERT INTO ConferenceMembership VALUES (101,999,1,2027);''')
        self.assertEqual(self.service.get_week_roster_violations(10, 100), [])
        self.assertEqual(self.service.get_week_roster_violations(10, 101),
            [{'memberId':11,'sportConferenceId':500,'count':2,'maxTeamsPerOwner':1}])
        self.db.connection.execute('UPDATE LeagueTeamSlot SET droppedWeek=2 WHERE id=1')
        self.db.connection.commit()
        self.assertEqual(self.service.get_week_roster_violations(10, 101), [])

    def test_empty_roster_does_not_validate_unrelated_invalid_configuration(self):
        self.cap(None)
        self.db.connection.execute('UPDATE LeagueTeamSlot SET droppedWeek=1 WHERE leagueId=10')
        self.db.connection.commit()
        self.assertEqual(self.service.get_week_roster_violations(10, 100), [])

    def test_zero_cap_drop_can_reduce_roster_while_still_over_cap(self):
        self.cap(0)
        self.db.connection.execute("INSERT INTO LeagueTeamSlot VALUES (4,10,11,103,1,NULL,'Draft')")
        self.db.connection.commit()
        result = self.service.free_agency_add_drop(10, 101, 2, 11, None, 101)
        self.service.apply_free_agent_transaction(result['transactionId'])
        self.assertEqual(result['memberRosterTeamIds'], [103])
        violations = self.service.get_week_roster_violations(10, 101)
        self.assertIn({'memberId':11,'sportConferenceId':500,'count':1,'maxTeamsPerOwner':0}, violations)

    def test_cap_failure_after_slot_closure_rolls_back_supplied_transaction(self):
        self.cap(1)
        self.db.connection.execute('''INSERT INTO "Transaction"
            (id,leagueId,weekId,type,memberFromId,memberToId,status,fromTeamIds,toTeamIds)
            VALUES (1,10,101,'FREE_AGENT',11,11,'PENDING_APPLY','[101]','[103]')''')
        self.db.connection.commit()
        before = self.state()
        def change_cap(sql):
            if 'UPDATE "LeagueTeamSlot"' in sql and '"droppedWeek"' in sql:
                self.db.before_query = None
                self.db.connection.execute('UPDATE SportConference SET maxTeamsPerOwner=NULL WHERE id=500')
        self.db.before_query = change_cap
        engine = transaction_fixture.ConnectionOwner(self.db)
        from endpoints.transaction.workflow_service import TransactionWorkflowService
        with self.assertRaisesRegex(ValueError, 'configuration'):
            with engine.begin() as conn:
                TransactionWorkflowService(engine).apply_free_agent_transaction(1, conn=conn)
        self.assertEqual(self.state(), before)
        self.assertEqual(self.db.connection.execute('SELECT maxTeamsPerOwner FROM SportConference WHERE id=500').fetchone()[0], 1)
        self.assertEqual((engine.begins, engine.connects), (1, 0))
