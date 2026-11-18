"""No network/configured app: MOD017 query capture, guard and owned cleanup contracts."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts/modernization'))

class Mod017Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import measure_mod017
        cls.m = measure_mod017

    def test_refuses_nonlocal_unmarked_and_unowned_targets(self):
        for host, port, marker in [('example.test',55439,self.m.MARKER),('127.0.0.1',5432,self.m.MARKER),('127.0.0.1',55439,'production')]:
            with self.assertRaises(RuntimeError): self.m.guard_target(host,port,marker)
        self.m.guard_target('127.0.0.1',55439,self.m.MARKER)
        for name in ['postgres','otm_mod017_other','otm_mod017_'+'x'*32]:
            with self.assertRaises(RuntimeError): self.m.cleanup_owned_database(MagicMock(),name,True)

    def test_cleanup_runs_only_for_created_uuid_even_on_failure(self):
        admin=MagicMock()
        admin.cursor.return_value.__enter__.return_value.fetchone.return_value=(self.m.MARKER,)
        name='otm_mod017_'+'a'*32
        with patch.object(self.m,'new_database_name',return_value=name):
            with self.assertRaisesRegex(ValueError,'injected'):
                with self.m.owned_database(admin): raise ValueError('injected')
        calls=admin.cursor.return_value.__enter__.return_value.execute.call_args_list
        self.assertTrue(any('CREATE DATABASE' in str(c) for c in calls))
        self.assertTrue(any('DROP DATABASE' in str(c) and name in str(c) for c in calls))
        admin.reset_mock()
        self.m.cleanup_owned_database(admin,name,False)
        admin.cursor.assert_not_called()

    def test_query_capture_preserves_actual_parameters_and_null_semantics(self):
        cases=self.m.capture_queries(100)
        self.assertEqual(len(cases),13)
        by_name={c['name']:c for c in cases}
        self.assertEqual(by_name['own_hot_active']['params'],{'user_id':1})
        self.assertIn("l.status <> 'Completed'",by_name['own_hot_active']['sql'])
        self.assertIn('SUM(wts."pointsAwarded")',by_name['own_hot_all']['sql'])
        self.assertNotIn('member_id',by_name['ownership_any_current']['params'])
        self.assertIsNone(by_name['ownership_null_member']['params']['member_id'])
        self.assertIn('lts."memberId" = :member_id',by_name['ownership_null_member']['sql'])
        self.assertIn('lts."droppedWeek" > :week_number',by_name['ownership_member_history']['sql'])
        self.assertEqual(by_name['ownership_member_history']['params']['week_number'],4)

    def test_fixture_sql_has_no_accidental_binds_in_json_literals(self):
        from datetime import datetime, timezone
        from sqlalchemy import text
        outer=self
        class Connection:
            def execute(self,statement,params=None):
                outer.assertLessEqual(set(statement.compile().params),{'anchor'})
                result=MagicMock();result.scalar_one.return_value=datetime.now(timezone.utc);return result
            def exec_driver_sql(self,statement):
                result=MagicMock()
                if statement.startswith('SELECT count(*)'):
                    result.scalar_one.return_value=outer.m.expected_counts(100)[statement.split('"')[1]]
                return result
            def commit(self):pass
        self.m.seed(Connection(),100)

    def test_cardinalities_and_result_equivalence_fail_closed(self):
        self.assertEqual(self.m.expected_counts(100),{'League':100,'LeagueMember':800,'Week':1300,'WeeklyTeamScore':9600,'LeagueTeamSlot':16000})
        a=self.m.signature([{'id':1,'name':'Synthetic'}])
        self.m.assert_equivalent(a,a)
        for other in [[{'id':2,'name':'Synthetic'}],[],[{'id':1,'name':'Different'}]]:
            with self.assertRaises(AssertionError):self.m.assert_equivalent(a,self.m.signature(other))

if __name__=='__main__':unittest.main()
