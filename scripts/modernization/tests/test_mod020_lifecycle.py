import importlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class LifecycleMeasureTests(unittest.TestCase):
 def setUp(self):self.m=importlib.import_module('measure_mod020_lifecycle')
 def test_group_states_and_write_churn_formula(self):
  m=self.m
  self.assertEqual(m.final_status(7),'Completed');self.assertEqual(m.initial_status(7),'Completed')
  self.assertEqual(m.expected_phase_rows(100,'dirty'),{'pre':20,'drafting':30,'post':10,'in_season':10,'completed':20})
  self.assertEqual(m.expected_phase_rows(100,'steady'),{'pre':0,'drafting':10,'post':0,'in_season':0,'completed':10})
  self.assertEqual(len(m.expected_touched(100,'dirty')),80);self.assertEqual(m.expected_touched(100,'steady'),list(range(7,101,10)))
 def test_no_final_status_change_for_completed_live_group(self):
  m=self.m
  self.assertEqual([m.final_status(i) for i in range(1,11)],['Pre-Draft','Drafting','Drafting','Post-Draft','In-Season','Completed','Completed','Completed','In-Season','Pre-Draft'])
  self.assertEqual(len(m.expected_status_changes(100,'dirty')),70);self.assertEqual(m.expected_status_changes(100,'steady'),[])
 def test_scoped_business_projections(self):
  m=self.m;self.assertIsNone(m.expected_read('denied'));self.assertIsNone(m.expected_read('missing'))
  self.assertEqual(m.expected_read('mine')[0]['memberId'],2);self.assertEqual(m.expected_read('detail')['status'],'Pre-Draft')
 def test_read_signature_counts_resources_not_dictionary_keys(self):
  m=self.m
  self.assertEqual(m.read_signature(None)['rows'],0)
  self.assertEqual(m.read_signature(m.expected_read('detail'))['rows'],1)
  self.assertEqual(m.read_signature(m.expected_read('mine'))['rows'],1)
 def test_classifier_observes_global_updates(self):
  self.assertEqual(self.m.classify('UPDATE "League" l SET status = \'Drafting\''),'drafting')
  self.assertEqual(self.m.classify('SELECT l.*, w.id AS "currentWeekId" FROM "League" l'),'read')
  with self.assertRaises(AssertionError):self.m.classify('SELECT unexpected')
 def test_provenance_failure_replaces_pass(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);mf=p/'current.json';mf.write_text('{"result":"PASS"}');connect=MagicMock()
   with patch.object(self.m.base,'ROOT',p/'missing'):
    with self.assertRaises(FileNotFoundError):self.m.run(p,mf,[100],connect)
   connect.assert_not_called();self.assertEqual(json.loads(mf.read_text())['result'],'FAILED')
if __name__=='__main__':unittest.main()
