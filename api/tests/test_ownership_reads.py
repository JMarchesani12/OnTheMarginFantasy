"""Actual draft/free-agency read equivalence; SQLite cannot establish PG locks/RLS."""
import unittest
from unittest.mock import patch
from endpoints.draft.pick_repository import DraftPickRepository
from endpoints.transaction.workflow_repository import TransactionWorkflowRepository
import test_live_pick_authorization as fixture


class OwnershipReadCharacterizationTests(unittest.TestCase):
    def setUp(self):
        self.db = fixture.LivePickDatabase()
        self.addCleanup(self.db.connection.close)
        self.draft = DraftPickRepository()
        self.workflow = TransactionWorkflowRepository()
        self.db.connection.executescript('''
            CREATE TABLE League (id INTEGER PRIMARY KEY,seasonYear INTEGER,sport INTEGER);
            INSERT INTO League VALUES (10,2026,1),(20,2025,1),(30,NULL,1);
            CREATE TABLE SportTeam (id INTEGER PRIMARY KEY,sportId INTEGER);
            INSERT INTO SportTeam VALUES (101,1),(102,1),(103,1),(104,2),(105,1),(106,1),(201,2);
            CREATE TABLE SportConference (id INTEGER PRIMARY KEY,sportId INTEGER,maxTeamsPerOwner INTEGER);
            INSERT INTO SportConference VALUES (501,1,3),(502,1,2),(601,2,1);
            CREATE TABLE ConferenceMembership (sportTeamId INTEGER,sportId INTEGER,seasonYear INTEGER,sportConferenceId INTEGER);
            INSERT INTO ConferenceMembership VALUES (101,1,NULL,501),(101,1,2026,502),
                (102,1,NULL,501),(102,1,2027,502),(103,1,NULL,501),(103,1,2026,999),
                (104,1,NULL,501),(105,1,NULL,501),(106,1,2025,502),(201,2,NULL,601);
            CREATE TABLE LeagueTeamSlot (leagueId INTEGER,memberId INTEGER,sportTeamId INTEGER,acquiredWeek INTEGER,droppedWeek INTEGER);
            INSERT INTO LeagueTeamSlot VALUES (10,11,101,0,NULL),(10,11,102,1,NULL),
                (10,12,105,1,NULL),(20,21,101,1,NULL);
        ''')

    def scalar(self, conference, week=1, league=10, member=11):
        row = self.draft.member_conference_count(self.db, {'leagueId':league,'memberId':member,
            'weekNumber':week,'sportConferenceId':conference}).fetchone()
        self.assertIsNotNone(row, 'scalar count always returns a row, even zero')
        return row._mapping['cnt']

    def grouped(self, week=1, league=10, member=11):
        rows = self.workflow.member_conference_counts(self.db, {'league_id':league,
            'member_id':member,'week_number':week}).mappings().all()
        return {row['sportConferenceId']:row['cnt'] for row in rows}

    def ownership(self, league=10, team=102, week=1, member=None):
        camel = {'leagueId':league,'sportTeamId':team,'week':week}
        snake = {'league_id':league,'team_id':team,'week_number':week}
        expected = bool(self.draft.live_team_ownership(self.db, camel).fetchone())
        self.assertEqual(bool(self.draft.manual_team_ownership(self.db, camel).fetchone()), expected)
        self.assertEqual(bool(self.workflow.team_owned(self.db, snake).fetchone()), expected)
        if member is not None:
            snake['member_id'] = member
            return bool(self.workflow.member_team_owned(self.db, snake).fetchone())
        return expected

    def test_ownership_isolates_league_team_member_and_week_zero(self):
        self.assertTrue(self.ownership(team=101, week=0))
        self.assertFalse(self.ownership(team=102, week=0))
        self.assertTrue(self.ownership(member=11))
        self.assertFalse(self.ownership(member=12))
        self.assertFalse(self.ownership(league=20, team=102))
        self.assertFalse(self.ownership(team=999))

    def test_scalar_and_grouped_scopes_and_zero_empty_shapes(self):
        self.assertEqual((self.scalar(501), self.scalar(502)), (1, 1))
        self.assertEqual(self.grouped(), {501:1,502:1})
        self.assertEqual(self.grouped(member=12), {501:1})
        self.assertEqual(self.scalar(501, member=999), 0)
        self.assertEqual(self.grouped(member=999), {})
        self.assertEqual(self.scalar(999), 0)
        self.assertEqual(self.grouped(league=20, member=21), {501:1})

    def test_acquired_and_dropped_equalities_empty_and_future_history(self):
        self.db.connection.executescript('''INSERT INTO LeagueTeamSlot VALUES
            (10,11,105,1,2),(10,11,105,3,NULL),(10,11,106,1,1);''')
        self.assertEqual([self.scalar(501, week=w) for w in (0,1,2,3)], [0,2,1,2])
        self.assertEqual([self.grouped(week=w) for w in (0,1,2,3)],
            [{502:1},{501:2,502:1},{501:1,502:1},{501:2,502:1}])
        self.assertTrue(self.ownership(team=105, week=1, member=11))
        self.assertFalse(self.ownership(team=105, week=2, member=11))
        self.assertTrue(self.ownership(team=105, week=3, member=11))
        self.assertFalse(self.ownership(team=106, week=1))

    def test_season_override_current_fallback_future_membership_and_null_season(self):
        self.assertEqual(self.grouped(), {501:1,502:1})
        self.db.connection.executescript('''INSERT INTO LeagueTeamSlot VALUES (30,31,101,1,NULL);''')
        self.assertEqual(self.grouped(league=30, member=31), {501:1})
        self.assertEqual((self.scalar(501, league=30, member=31), self.scalar(502, league=30, member=31)), (1,0))
        self.db.connection.execute('UPDATE League SET seasonYear=2027 WHERE id=10')
        self.assertEqual(self.grouped(), {501:1,502:1})  # 101 falls back; 102 changes conference.
        self.assertEqual(self.scalar(501), 1)

    def test_invalid_seasonal_missing_and_cross_sport_mappings_are_omitted_not_fallback(self):
        self.db.connection.executescript('''INSERT INTO LeagueTeamSlot VALUES
            (10,11,103,1,NULL),(10,11,104,1,NULL),(10,11,106,1,NULL),(10,11,999,1,NULL);''')
        self.assertEqual((self.scalar(501), self.scalar(502)), (1,1))
        self.assertEqual(self.grouped(), {501:1,502:1})
        from utils.conference_membership import require_member_roster_mappings
        with self.assertRaisesRegex(ValueError, 'configuration'):
            require_member_roster_mappings(self.db, 10, [11], 1)

    def test_legacy_duplicate_intervals_remain_distinct_for_draft_and_rows_for_free_agency(self):
        self.db.connection.execute('INSERT INTO LeagueTeamSlot VALUES (10,11,102,1,NULL)')
        self.assertEqual(self.scalar(501), 1)
        self.assertEqual(self.grouped(), {501:2,502:1})

    def test_raw_orphan_league_semantics_are_preserved_not_an_authorization_grant(self):
        self.db.connection.execute('INSERT INTO LeagueTeamSlot VALUES (999,91,102,1,NULL)')
        self.assertTrue(self.ownership(league=999, member=91))
        self.assertEqual(self.scalar(501, league=999, member=91), 0)
        self.assertEqual(self.grouped(league=999, member=91), {501:1})

    def test_raw_valid_other_sport_mapping_retained_but_service_guard_rejects_wrong_league_sport(self):
        self.db.connection.execute('INSERT INTO LeagueTeamSlot VALUES (10,11,201,1,NULL)')
        self.assertEqual(self.scalar(601), 1)
        self.assertEqual(self.grouped(), {501:1,502:1,601:1})
        from utils.conference_membership import require_member_roster_mappings
        with self.assertRaisesRegex(ValueError, 'configuration'):
            require_member_roster_mappings(self.db, 10, [11], 1)

    def test_null_member_on_member_scoped_read_does_not_become_global_ownership(self):
        row = self.workflow.member_team_owned(self.db, {'league_id':10,'member_id':None,'team_id':102,'week_number':1}).fetchone()
        self.assertIsNone(row)

    def test_each_repository_read_executes_one_statement(self):
        calls = [(self.draft.live_team_ownership, {'leagueId':10,'sportTeamId':102,'week':1}),
                 (self.draft.manual_team_ownership, {'leagueId':10,'sportTeamId':102,'week':1}),
                 (self.draft.member_conference_count, {'leagueId':10,'memberId':11,'weekNumber':1,'sportConferenceId':501}),
                 (self.workflow.team_owned, {'league_id':10,'team_id':102,'week_number':1}),
                 (self.workflow.member_team_owned, {'league_id':10,'member_id':11,'team_id':102,'week_number':1}),
                 (self.workflow.member_conference_counts, {'league_id':10,'member_id':11,'week_number':1})]
        for call, params in calls:
            before = len(self.db.queries)
            call(self.db, params)
            self.assertEqual(len(self.db.queries) - before, 1)


class OwnershipReadDelegationTests(unittest.TestCase):
    def cases(self, conn):
        return [
            (DraftPickRepository().live_team_ownership, {'leagueId':10,'sportTeamId':102,'week':1}, 'team_ownership_rows', (conn,10,102,1), {}),
            (DraftPickRepository().manual_team_ownership, {'leagueId':10,'sportTeamId':102,'week':1}, 'team_ownership_rows', (conn,10,102,1), {}),
            (DraftPickRepository().member_conference_count, {'leagueId':10,'memberId':11,'weekNumber':1,'sportConferenceId':501}, 'distinct_conference_count_rows', (conn,10,11,1,501), {}),
            (TransactionWorkflowRepository().team_owned, {'league_id':10,'team_id':102,'week_number':1}, 'team_ownership_rows', (conn,10,102,1), {}),
            (TransactionWorkflowRepository().member_team_owned, {'league_id':10,'member_id':11,'team_id':102,'week_number':1}, 'team_ownership_rows', (conn,10,102,1), {'member_id':11}),
            (TransactionWorkflowRepository().member_conference_counts, {'league_id':10,'member_id':11,'week_number':1}, 'grouped_conference_count_rows', (conn,10,11,1), {}),
        ]

    def test_six_adapters_delegate_same_connection_and_return_unconsumed_result(self):
        from utils import ownership_reads
        conn, result = object(), object()
        for method, params, helper, args, kwargs in self.cases(conn):
            with self.subTest(method=method.__name__), patch.object(ownership_reads, helper, return_value=result) as read:
                self.assertIs(method(conn, params), result)
                read.assert_called_once_with(*args, **kwargs)

    def test_six_adapters_propagate_sql_failure_without_recovery_or_consumption(self):
        from utils import ownership_reads
        conn = object()
        for method, params, helper, args, kwargs in self.cases(conn):
            failure = RuntimeError('synthetic shared read failure')
            with self.subTest(method=method.__name__), patch.object(ownership_reads, helper, side_effect=failure) as read:
                with self.assertRaises(RuntimeError) as caught:
                    method(conn, params)
                self.assertIs(caught.exception, failure)
                read.assert_called_once_with(*args, **kwargs)

    def test_helpers_only_execute_fixed_bound_sql_on_supplied_connection(self):
        from utils import ownership_reads
        result = object()
        class Connection:
            def __init__(self): self.calls = []
            def execute(self, statement, params):
                self.calls.append((str(statement), params))
                return result
        conn = Connection()
        malicious_team = '102 OR 1=1'
        self.assertIs(ownership_reads.team_ownership_rows(conn,10,malicious_team,0), result)
        self.assertNotIn(malicious_team, conn.calls[0][0])
        self.assertEqual(conn.calls[0][1]['team_id'], malicious_team)
        self.assertIs(ownership_reads.team_ownership_rows(conn,10,102,1,member_id=11), result)
        self.assertIs(ownership_reads.distinct_conference_count_rows(conn,10,11,1,501), result)
        self.assertIs(ownership_reads.grouped_conference_count_rows(conn,10,11,1), result)
        self.assertEqual(len(conn.calls), 4)


class DraftOwnershipReadIntegrationTests(unittest.TestCase):
    def setUp(self):
        import test_transaction_service as transactions
        from endpoints.draft.pick_service import DraftPickService
        base = fixture.LivePickAuthorizationTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db, self.state = base.db, base.state
        self.engine = transactions.ConnectionOwner(self.db)
        self.service = DraftPickService(self.engine)

    def assert_allocation(self, call, week):
        from utils import ownership_reads
        ownership, count = ownership_reads.team_ownership_rows, ownership_reads.distinct_conference_count_rows
        seen = []
        def capture(kind, original):
            def read(*args, **kwargs):
                self.assertIs(args[0], self.db)
                self.assertEqual(self.engine.active, 1)
                seen.append((kind, args))
                return original(*args, **kwargs)
            return read
        with patch.object(ownership_reads, 'team_ownership_rows', side_effect=capture('owner', ownership)), \
             patch.object(ownership_reads, 'distinct_conference_count_rows', side_effect=capture('count', count)):
            result = call()
        self.assertEqual((result['memberId'], result['sportTeamId']), (12,102))
        self.assertEqual([kind for kind, args in seen], ['owner','count'])
        self.assertEqual(seen[0][1][3], week)
        self.assertEqual(seen[1][1][3], week)
        self.assertEqual(self.state()['LeagueTeamSlot'][0]['acquiredWeek'], week)
        self.assertEqual((self.engine.begins, self.engine.connects), (1,0))

    def test_live_explicit_week_uses_shared_reads_inside_owned_transaction(self):
        from actors import UserActor
        self.assert_allocation(lambda: self.service.pick_live(UserActor(2,'bob'),10,12,102,acquired_week=3), 3)

    def test_manual_default_week_uses_same_reads_without_enabling_http(self):
        self.assert_allocation(lambda: self.service.allocate_manual_for_job(10,12,102), 1)


class FreeAgentOwnershipReadIntegrationTests(unittest.TestCase):
    def setUp(self):
        import test_free_agency_authorization as free
        import test_operational_trusted_contract as operational
        import test_transaction_service as transactions
        from endpoints.transaction.workflow_service import TransactionWorkflowService
        base = free.FreeAgencyAuthorizationTests()
        base.database_type = operational.ApplyDatabase
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db, self.state = base.db, base.state
        self.db.connection.execute('UPDATE SportConference SET maxTeamsPerOwner=1')
        self.db.connection.commit()
        self.engine = transactions.ConnectionOwner(self.db)
        self.service = TransactionWorkflowService(self.engine)

    def test_reservation_and_application_read_caller_state_before_and_after_drop(self):
        from actors import UserActor
        from utils import ownership_reads
        original = ownership_reads.grouped_conference_count_rows
        observed = []
        def read(conn, league, member, week):
            self.assertIs(conn, self.db)
            self.assertEqual(self.engine.active, 1)
            dropped = self.db.connection.execute('SELECT droppedWeek FROM LeagueTeamSlot WHERE id=1').fetchone()[0]
            observed.append((league,member,week,dropped))
            return original(conn,league,member,week)
        with patch.object(ownership_reads, 'grouped_conference_count_rows', side_effect=read):
            result = self.service.free_agency(UserActor(1,'alice'),10,101,99,11,103,101)
            self.assertEqual(result['status'], 'PENDING_APPLY')
            with self.engine.begin() as conn:
                self.service.apply_free_agent_transaction(result['transactionId'], conn=conn)
        self.assertEqual(observed, [(10,11,2,None),(10,11,2,2)])
        self.assertEqual((self.engine.begins, self.engine.connects), (2,0))
        slots = self.state()['LeagueTeamSlot']
        self.assertEqual((slots[0]['droppedWeek'],slots[-1]['acquiredWeek'],slots[-1]['sportTeamId']), (2,2,103))
        self.assertEqual(self.state()['Transaction'][0]['status'], 'COMPLETED')

    def test_shared_count_failure_after_closure_rolls_back_and_leaves_pending(self):
        from utils import ownership_reads
        self.db.connection.execute('''INSERT INTO "Transaction"
            (id,leagueId,weekId,type,memberFromId,memberToId,status,fromTeamIds,toTeamIds)
            VALUES (1,10,101,'FREE_AGENT',11,11,'PENDING_APPLY','[101]','[103]')''')
        self.db.connection.commit()
        before = self.state()
        failure = RuntimeError('synthetic count read failure after drop')
        def fail(conn, league, member, week):
            self.assertIs(conn, self.db)
            self.assertEqual(self.engine.active, 1)
            self.assertEqual(self.db.connection.execute('SELECT droppedWeek FROM LeagueTeamSlot WHERE id=1').fetchone()[0], 2)
            raise failure
        with patch.object(ownership_reads, 'grouped_conference_count_rows', side_effect=fail):
            with self.assertRaises(RuntimeError) as caught:
                with self.engine.begin() as conn:
                    self.service.apply_free_agent_transaction(1, conn=conn)
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.state(), before)
        self.assertEqual((self.engine.begins, self.engine.connects), (1,0))
