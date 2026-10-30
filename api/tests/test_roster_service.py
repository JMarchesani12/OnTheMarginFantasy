"""Real roster SQL through direct service entry points, no live database."""
import unittest

from actors import UserActor
from endpoints.roster.service import RosterService
from endpoints.roster.contracts import RosterAccessDenied, RosterWeekUnavailable
import test_roster_available_authorization as fixture
from test_transaction_service import ConnectionOwner


class RosterServiceTests(unittest.TestCase):
    def setUp(self):
        base = fixture.AvailableAuthorizationTests()
        base.setUp()
        self.addCleanup(base.doCleanups)
        self.db = base.db
        self.engine = ConnectionOwner(self.db)
        self.service = RosterService(self.engine)

    def test_both_interactive_reads_require_actor_before_io(self):
        for actor in (None, 1, {'user_id': 1}):
            for operation, args in ((self.service.get_member_teams_for_week, (10,12,1)),
                                    (self.service.get_available_teams_for_week, (10,1))):
                with self.assertRaises(TypeError):
                    operation(actor, *args)
        self.assertEqual(self.engine.connects, 0)

    def test_one_connection_per_read_preserves_locked_week_and_pending_move_filters(self):
        member = self.service.get_member_teams_for_week(UserActor(1,'alice'), 10, 12, 1)
        self.assertEqual([r['sportTeamId'] for r in member], [101])
        self.assertEqual(self.engine.connects, 1)
        available = self.service.get_available_teams_for_week(UserActor(2,'bob'), 10, 1)
        self.assertEqual({r['id'] for r in available}, {101,102})
        self.assertEqual(self.engine.connects, 2)
        self.assertEqual(self.engine.begins, 0)

    def test_commissioner_reads_and_member_resource_scope_remain_distinct(self):
        self.assertEqual(self.service.get_member_teams_for_week(UserActor(1,'alice'), 30,31,1), [])
        self.service.get_available_teams_for_week(UserActor(1,'alice'), 30,1)
        queries=[]
        self.db.before_query=queries.append
        for operation,args in ((self.service.get_member_teams_for_week,(10,21,1)),
                               (self.service.get_available_teams_for_week,(20,1))):
            with self.assertRaises(RosterAccessDenied):
                operation(UserActor(1,'alice'),*args)
        self.assertFalse(any('FROM "Week"' in sql or 'WITH pending_adds' in sql for sql in queries))

    def test_membership_revocation_on_final_query_exposes_no_rows(self):
        for marker,operation,args in (
                ('WITH league_info', self.service.get_member_teams_for_week,(10,12,1)),
                ('WITH pending_adds', self.service.get_available_teams_for_week,(10,1))):
            def revoke(sql):
                if marker in sql:
                    self.db.before_query=None
                    self.db.connection.execute('DELETE FROM LeagueMember WHERE id=12')
            self.db.before_query=revoke
            self.assertEqual(operation(UserActor(2,'bob'),*args), [])
            self.db.connection.execute('INSERT INTO LeagueMember VALUES (12,10,2)')
            self.db.connection.commit()

    def test_target_member_removed_after_access_check_suppresses_roster(self):
        def remove(sql):
            if 'WITH league_info' in sql:
                self.db.before_query=None
                self.db.connection.execute('DELETE FROM LeagueMember WHERE id=12')
        self.db.before_query=remove
        self.assertEqual(self.service.get_member_teams_for_week(UserActor(1,'alice'),10,12,1), [])

    def test_no_future_unlocked_week_has_domain_failure_and_legacy_value_error(self):
        self.db.connection.execute('DELETE FROM Week WHERE id=101')
        self.db.connection.commit()
        for operation,args in ((self.service.get_member_teams_for_week,(10,12,1)),
                               (self.service.get_available_teams_for_week,(10,1))):
            with self.assertRaisesRegex(RosterWeekUnavailable,'No unlocked future week found after week 1'):
                operation(UserActor(1,'alice'),*args)
        from endpoints.roster.rosterModel import RosterModel
        with self.assertRaisesRegex(ValueError,'No unlocked future week'):
            RosterModel(self.db).get_member_teams_for_week(10,12,1)

    def test_missing_week_and_explicit_trusted_reads_keep_existing_semantics(self):
        self.db.connection.execute('DELETE FROM Week WHERE leagueId=10')
        self.db.connection.commit()
        available=self.service.get_available_teams_for_week(UserActor(1,'alice'),10,1)
        self.assertEqual({r['id'] for r in available},{102,103})
        self.assertEqual(self.service.get_available_teams_for_job(999,1),[])
        self.assertEqual(self.service.get_member_teams_for_job(20,21,1)[0]['slotId'],2)
