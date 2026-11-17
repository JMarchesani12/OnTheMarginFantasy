import importlib,json,sys,tempfile,unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch,MagicMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class LookupTests(unittest.TestCase):
 def setUp(self):self.m=importlib.import_module('measure_mod017_lookup')
 def test_capture_and_exact_values(self):
  c={x['name']:x for x in self.m.capture_queries(100)}
  self.assertEqual(len(c),12)
  self.assertIn('ORDER BY st."displayName"',c['lookup_current']['sql'])
  self.assertEqual(c['lookup_current']['expected_rows'],512)
  self.assertEqual(c['distinct_current_one']['expected_values'],[{'cnt':3}])
  self.assertEqual(c['distinct_history_one']['expected_values'],[{'cnt':4}])
  self.assertEqual(c['group_current']['expected_values'],[{'sportConferenceId':1,'cnt':3},{'sportConferenceId':2,'cnt':1}])
 def test_group_order_only_is_normalized(self):
  rows=[{'sportConferenceId':2,'cnt':1},{'sportConferenceId':1,'cnt':3}]
  self.assertEqual(self.m.normalize_rows('group',rows),list(reversed(rows)))
  self.assertEqual(self.m.normalize_rows('lookup',rows),rows)
 def test_actual_ranking_short_query_and_abbreviation(self):
  class Row:
   def __init__(self,value):self._mapping=value
  class Result:
   def __init__(self,rows):self.rows=[Row(r) for r in rows]
   def fetchall(self):return self.rows
   def fetchone(self):return self.rows[0]
  calls=[]
  class Repo:
   def search_league_context(self,c,p):calls.append('context');return Result([{'sport':1,'seasonYear':2026,'weekNumber':13}])
   def search_teams(self,c,p):calls.append('teams');return Result([{'teamId':1,'teamName':'Iowa State'},{'teamId':2,'teamName':'Duke'},{'teamId':3,'teamName':'State University'}])
  db=MagicMock();db.begin.side_effect=lambda:nullcontext(None)
  service=self.m.ScheduleReadService(db,repository=Repo())
  self.assertEqual(service.search_teams_for_league(1,'i'),[]);self.assertEqual(calls,[])
  self.assertEqual([r['teamId'] for r in service.search_teams_for_league(1,'iowa st')],[1])
  self.assertEqual(calls,['context','teams'])
 def test_provenance_failure_records_failed_without_connect(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d);manifest=path/'current.json';manifest.write_text('{"result":"PASS"}');connect=MagicMock()
   with patch.object(self.m.base,'ROOT',path/'missing'):
    with self.assertRaises(FileNotFoundError):self.m.run(path,manifest,[100],connect)
   connect.assert_not_called();self.assertEqual(json.loads(manifest.read_text())['result'],'FAILED')
if __name__=='__main__':unittest.main()
