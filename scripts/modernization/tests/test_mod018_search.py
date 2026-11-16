import importlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class SearchMeasureTests(unittest.TestCase):
 def setUp(self):self.m=importlib.import_module('measure_mod018_search')
 def test_capture_preserves_source_and_isolates_tie_probe(self):
  cases=self.m.capture_queries(1000);self.assertEqual(len(cases),6)
  for c in cases:
   self.assertIn('ORDER BY similarity(l.name, :q) DESC, l.name ASC',c['sql']);self.assertNotIn('l.id ASC',c['sql']);self.assertIn('l.name ASC, l.id ASC',self.m.probe_sql(c['sql']));self.assertLessEqual(c['params']['offset'],10000)
 def test_independent_payload_and_scope(self):
  m=self.m;ids=m.eligible_ids(1000,None);self.assertEqual(len(ids),700);self.assertNotIn(10,ids)
  self.assertTrue(all(i%7==0 for i in m.eligible_ids(1000,2)))
  self.assertEqual(m.expected_row(1),{'id':1,'name':'Audit League','sport':1,'numPlayers':8,'status':'Pre-Draft','draftDate':None,'isDiscoverable':True,'commissioner':1,'commissionerDisplayName':'Audit commissioner'})
 def test_reference_page_order_and_empty_deep_page(self):
  m=self.m;cases={x['name']:x for x in m.capture_queries(1000)}
  self.assertEqual(m.expected_ids(1000,cases['all_first']),list(range(1,8))+list(range(11,18))+list(range(21,28))+list(range(31,38))+list(range(41,48))+list(range(51,58))+list(range(61,68))+[71])
  self.assertEqual(m.expected_ids(1000,cases['all_max_offset']),[])
 def test_actual_service_short_query_and_clamps(self):
  m=self.m;engine=MagicMock();repo=MagicMock();service=m.LeagueReadService(engine,repository=repo)
  self.assertEqual(service.search_public(' a '),[]);engine.begin.assert_not_called()
  service.search_public(' Audit League ',limit=100,offset=-2);args=repo.search_discoverable.call_args.args;self.assertEqual(args[1:],('Audit League',None,50,0))
 def test_provenance_failure_overwrites_previous_pass(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);mf=p/'current.json';mf.write_text('{"result":"PASS"}');connect=MagicMock()
   with patch.object(self.m.base,'ROOT',p/'missing'):
    with self.assertRaises(FileNotFoundError):self.m.run(p,mf,[1000],connect)
   connect.assert_not_called();self.assertEqual(json.loads(mf.read_text())['result'],'FAILED')
if __name__=='__main__':unittest.main()
