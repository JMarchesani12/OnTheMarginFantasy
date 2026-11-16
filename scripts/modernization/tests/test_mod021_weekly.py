import importlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class WeeklyMeasureTests(unittest.TestCase):
 def setUp(self):self.m=importlib.import_module('measure_mod021_weekly')
 def test_counts_grow_with_pairs_and_fallback(self):
  for n,unique,tie in [(4,16,30),(8,28,72),(16,52,204)]:
   self.assertEqual(sum(self.m.expected_counts(n,'unique').values()),unique)
   self.assertEqual(sum(self.m.expected_counts(n,'unresolved').values()),tie)
   self.assertEqual(self.m.expected_counts(n,'head_decides')['head_to_head'],n*(n-1)//2)
   self.assertEqual(self.m.expected_counts(n,'margin')['settings'],2*n)
 def test_independent_result_order_totals_points(self):
  m=self.m
  self.assertEqual([r['memberId'] for r in m.expected_scores(4,'head_decides')],[1001,1003,1004,1002])
  self.assertEqual([r['memberId'] for r in m.expected_scores(4,'margin')],[1004,1003,1002,1001])
  self.assertEqual([r['pointDifferential'] for r in m.expected_scores(4,'tier_phase')],[12,9,6,3])
  self.assertEqual([r['pointsAwarded'] for r in m.expected_scores(4,'unresolved')],[4,3,2,1])
 def test_fixture_includes_both_orientations_double_owned_and_phase_loss(self):
  rows=self.m.fixture_games(4,'tier_phase')
  self.assertTrue(any(r['home']==32 for r in rows));self.assertTrue(any(r['away']==32 for r in rows))
  self.assertTrue(any(r['home']==1 and r['away']==5 for r in rows))
  self.assertTrue(any(r['margin']<0 for r in rows))
 def test_query_classification_fails_on_unknown(self):
  self.assertEqual(self.m.classify('INSERT INTO "WeeklyTeamScore" VALUES (1)'),'insert')
  self.assertEqual(self.m.classify('WITH target_week AS (a_teams AS ()) SELECT 1'),'head_to_head')
  with self.assertRaises(AssertionError):self.m.classify('SELECT unexpected')
 def test_phase_fixture_has_no_accidental_json_bind_parameters(self):
  conn=MagicMock();self.m.seed_scenario(conn,4,'tier_phase','2026-11-15T00:00:00+00:00')
  for call in conn.execute.call_args_list:
   required=set(call.args[0].compile().params);provided=set(call.args[1])
   self.assertLessEqual(required,provided)
 def test_provenance_failure_replaces_pass(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);mf=p/'current.json';mf.write_text('{"result":"PASS"}');connect=MagicMock()
   with patch.object(self.m.base,'ROOT',p/'missing'):
    with self.assertRaises(FileNotFoundError):self.m.run(p,mf,[4],connect)
   connect.assert_not_called();self.assertEqual(json.loads(mf.read_text())['result'],'FAILED')
if __name__=='__main__':unittest.main()
