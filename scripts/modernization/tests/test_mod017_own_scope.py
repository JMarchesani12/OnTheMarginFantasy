import importlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class OwnScopeAuditTests(unittest.TestCase):
 def test_failed_provenance_replaces_stale_pass_before_connect(self):
  m=importlib.import_module('verify_mod017_own_score_scope')
  with tempfile.TemporaryDirectory() as d:
   path=Path(d);manifest=path/'mod-017-own-scope-current-2026-11-16.json';manifest.write_text('{"result":"PASS"}');connect=MagicMock()
   with patch.object(m.base,'ROOT',path/'missing'):
    with self.assertRaises(FileNotFoundError):m.run(directory=path,tiers=[100],connect=connect)
   connect.assert_not_called();self.assertEqual(json.loads(manifest.read_text())['result'],'FAILED')
 def test_ordered_keys_and_equal_key_multiplicity_comparison(self):
  m=importlib.import_module('verify_mod017_own_score_scope')
  rows=[dict(leagueId=1,draftOrder=1,currentWeekId=2),dict(leagueId=1,draftOrder=1,currentWeekId=3),dict(leagueId=2,draftOrder=1,currentWeekId=None)]
  m.assert_results(rows,[rows[1],rows[0],rows[2]])
  with self.assertRaises(AssertionError):m.assert_results(rows,rows[::-1])
  with self.assertRaises(AssertionError):m.assert_results(rows,rows[:-1])

 def test_equal_numeric_values_cannot_hide_changed_result_type(self):
  m=importlib.import_module('verify_mod017_own_score_scope')
  with self.assertRaises(AssertionError):m.assert_results([dict(leagueId=1,draftOrder=1,seasonPoints=5)],[dict(leagueId=1,draftOrder=1,seasonPoints=5.0)])
