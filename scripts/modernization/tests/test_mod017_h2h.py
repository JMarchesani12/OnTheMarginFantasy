import importlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
ANCHOR='2026-11-15T12:00:00+00:00'
class HeadToHeadTests(unittest.TestCase):
 def setUp(self):self.m=importlib.import_module('measure_mod017_h2h')
 def test_capture_and_expected_cases(self):
  cases=self.m.capture_queries(100,ANCHOR);self.assertEqual(len(cases),11)
  for c in cases:
   self.assertIn('lts."acquiredWeek" <= :weekNumber',c['sql'])
   self.assertIn('lts."droppedWeek" > :weekNumber',c['sql'])
   self.assertIn('ORDER BY gr.date, gr."externalGameId"',c['sql'])
   self.assertEqual(c['expected_rows'],len(c['expected_values']))
  by={c['name']:c for c in cases}
  for name in ['current_ac','unknown','missing_week','missing_league','same_member']:self.assertEqual(by[name]['expected_rows'],0)
  self.assertGreater(by['current']['expected_rows'],0)
 def test_date_endpoints_and_half_open_transfer(self):
  m=self.m;cases={c['name']:c for c in m.capture_queries(100,ANCHOR)}
  before={r['id']:r for r in cases['before']['expected_values']}
  self.assertIn(1,before);self.assertIn(2,before);self.assertNotIn(3,before);self.assertNotIn(4,before)
  acquired=cases['acquired']['expected_values'];self.assertTrue(all(1 not in [r['homeTeamId'],r['awayTeamId']] for r in acquired))
  during=cases['during']['expected_values'];self.assertTrue(during);self.assertTrue(all(1 in [r['homeTeamId'],r['awayTeamId']] for r in during))
  returned={r['id'] for r in cases['returned']['expected_values']};self.assertIn(7,returned)
 def test_complete_orientation_and_swapped_flags(self):
  cases={c['name']:c for c in self.m.capture_queries(100,ANCHOR)}
  a=cases['current']['expected_values'];b=cases['swapped']['expected_values'];self.assertEqual([r['id'] for r in a],[r['id'] for r in b])
  self.assertTrue(any(r['homeOwnedByA'] for r in a));self.assertTrue(any(r['awayOwnedByA'] for r in a))
  for x,y in zip(a,b):
   self.assertEqual(x['homeOwnedByA'],y['homeOwnedByB']);self.assertEqual(x['awayOwnedByA'],y['awayOwnedByB'])
   self.assertTrue(x['homeTeamName'].startswith('Sport team '));self.assertIsInstance(x['homeScore'],int)
 def test_fixture_modulo_uses_sqlalchemy_text_not_raw_driver(self):
  conn=MagicMock();conn.execute.return_value.rowcount=1
  with patch.object(self.m.games,'seed_games',return_value={'games_per_season':500}):self.m.seed_head_to_head(conn,100,ANCHOR)
  for call in conn.exec_driver_sql.call_args_list:self.assertNotIn('%',call.args[0])
  self.assertTrue(any('WITH pairs AS' in str(call.args[0]) for call in conn.execute.call_args_list))
 def test_sample_count_is_enforced(self):
  c={'expected_rows':0};r={'result':{'rows':0},'client_execute_fetch_ms':{'samples':[1]*4}}
  with self.assertRaises(AssertionError):self.m.validate_result(c,r)
 def test_provenance_failure_overwrites_pass_before_connect(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);manifest=p/'current.json';manifest.write_text('{"result":"PASS"}');connect=MagicMock()
   with patch.object(self.m.base,'ROOT',p/'missing'):
    with self.assertRaises(FileNotFoundError):self.m.run(p,manifest,[100],connect)
   connect.assert_not_called();self.assertEqual(json.loads(manifest.read_text())['result'],'FAILED')
if __name__=='__main__':unittest.main()
