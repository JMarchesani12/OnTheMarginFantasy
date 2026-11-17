import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class IndexSelectionTests(unittest.TestCase):
    def setUp(self):self.m=importlib.import_module('mod017_index_support')
    def row(self):
        return dict(oid=42,name='mod017_final_team',schema='public',table_name='LeagueTeamSlot',method='btree',key_definitions=['"leagueId"','"sportTeamId"'],includes=['"memberId"','"acquiredWeek"','"droppedWeek"'],predicate=None,valid=True,ready=True,unique=False,primary=False,exclusion=False,constraints=[],operator_classes='1 2',collations='0 0',options='0 0',nulls_not_distinct=False)
    def test_signature_distinguishes_keys_order_include_predicate_and_validity(self):
        row=self.row();original=self.m.index_signature(row)
        for key,value in [('key_definitions',['"sportTeamId"','"leagueId"']),('includes',[]),('predicate','status = 1'),('valid',False),('ready',False),('constraints',['integrity']),('options','0 1')]:
            changed=dict(row);changed[key]=value
            self.assertNotEqual(original,self.m.index_signature(changed),key)
    def test_equivalent_other_name_is_not_a_new_candidate(self):
        a=self.row();b=dict(a,name='existing_other',oid=99)
        self.assertEqual(self.m.index_signature(a),self.m.index_signature(b))
        self.assertEqual(self.m.equivalent_indexes(a,[b]),[b])
    def test_teardown_refuses_unowned_or_constraint_index(self):
        row=self.row();self.m.assert_owned_index(row,{'mod017_final_team':42})
        for bad in [dict(row,name='baseline'),dict(row,constraints=['integrity']),dict(row,oid=43),dict(row,primary=True),dict(row,exclusion=True)]:
            with self.assertRaises(RuntimeError):self.m.assert_owned_index(bad,{'mod017_final_team':42})
    def test_incomplete_configuration_or_samples_cannot_pass(self):
        records=[dict(configuration='baseline',name='a',samples=[1]*5)]
        self.m.validate_matrix(records,[('baseline','a')])
        for bad in [[],records+records,[dict(records[0],samples=[1])]]:
            with self.assertRaises(AssertionError):self.m.validate_matrix(bad,[('baseline','a')])
    def test_provenance_failure_overwrites_stale_pass_before_connect(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'current.json').write_text('{"result":"PASS"}')
            with self.assertRaises(FileNotFoundError):
                with self.m.evidence_run(root,[root/'missing']) as report:self.fail('must fail before work')
            current=json.loads((root/'current.json').read_text())
            self.assertEqual(current['result'],'FAILED')
            self.assertEqual(json.loads((root/current['artifact']).read_text())['result'],'FAILED')
    def test_lookup_rejects_changed_owner_labels_and_covers_unknown_group(self):
        import measure_mod017_lookup as lookup
        cases={c['name']:c for c in lookup.capture_queries(100)}
        self.assertEqual(cases['group_unknown']['expected_values'],[])
        rows=[dict(teamId=i,ownerMemberId=None) for i in range(1,513)]
        rows[0].update(conferenceName='Conference 2',ownerMemberId=401,ownerTeamName='Team 1',ownerDisplayName='WRONG')
        with self.assertRaises(AssertionError):lookup.verify_lookup(rows,dict(sport=1,leagueId=51,seasonYear=2026),100)
    def test_current_batch_fixture_covers_transfer_and_absent(self):
        import compare_mod017_indexes as runner
        cases={c['name']:c for c in runner.group_cases(100,'2026-11-16T12:00:00+00:00')}
        self.assertGreater(cases['h2h_group_current']['expected_rows'],0)
        self.assertEqual(cases['h2h_group_unknown']['expected_values'],[])
        self.assertEqual(cases['h2h_group_absent']['expected_values'],[])
        self.assertTrue(all(401 not in r['homeMemberIds']+r['awayMemberIds'] for r in cases['h2h_group_transfer']['expected_values']))
    def test_dense_pending_open_trade_expectations_include_pending_trades(self):
        import compare_mod017_indexes as runner
        for density,count in [(.001,10),(.1,13),(.5,29)]:
            cases={c['name']:c for c in runner.transaction_cases(100,'2026-11-16T12:00:00+00:00',density,1)}
            self.assertEqual(cases['open_participant']['expected_rows'],count)
    def test_registry_has_only_approved_families_and_unique_case_names(self):
        self.assertEqual(set(self.m.CANDIDATES),{'team','member','game','pending','status','time'})
        import compare_mod017_indexes as runner
        cases=runner.ownership_cases(100,'2026-11-16T12:00:00+00:00')
        names=[c['name'] for c in cases]
        self.assertEqual(len(names),len(set(names)))
    def test_capture_preserves_expanding_own_scope(self):
        import compare_mod017_indexes as runner
        from sqlalchemy.dialects import postgresql
        cases={c['name']:c for c in runner.ownership_cases(100,'2026-11-16T12:00:00+00:00')}
        c=cases['own_supplied_sparse'];statement=runner.statement_for(c)
        compiled=statement.params(**c['params']).compile(dialect=postgresql.dialect(),compile_kwargs={'render_postcompile':True})
        self.assertNotIn('POSTCOMPILE',str(compiled));self.assertNotIn('IN ((',str(compiled))
        self.assertEqual(compiled.params['scope_ids_1'],1)
    def test_failed_run_reports_actual_database_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaisesRegex(ValueError,'injected'):
                with self.m.evidence_run(root,[]) as report:
                    report['databases'].append(dict(name='synthetic-owned',cleanup='removed'))
                    raise ValueError('injected')
            manifest=json.loads((root/'current.json').read_text())
            self.assertEqual(manifest['cleanup'],'verified')
