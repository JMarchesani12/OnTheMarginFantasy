import importlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
ANCHOR='2026-11-15T12:00:00+00:00'
class ScoreReadTests(unittest.TestCase):
 def setUp(self):self.m=importlib.import_module('measure_mod017_scores')
 def test_expansion_empty_and_duplicate_bindings(self):
  c={x['name']:x for x in self.m.capture_queries(100,ANCHOR)};self.assertEqual(len(c),15)
  for x in c.values():self.assertNotIn('POSTCOMPILE',x['sql'])
  self.assertIn('weekNumbers_1',c['weekly_one']['params']);self.assertEqual(c['weekly_duplicate']['expected_rows'],7)
  self.assertEqual(c['weekly_empty']['expected_rows'],0);self.assertEqual(c['weekly_all']['expected_rows'],84)
  self.assertIn('ORDER BY w."weekNumber" ASC, wts.rank ASC',c['weekly_all']['sql'])
 def test_full_values_zero_member_and_scope(self):
  c={x['name']:x for x in self.m.capture_queries(100,ANCHOR)};league=51;member=401
  self.assertEqual(c['season_current']['expected_values'][-1],{'memberId':408,'teamName':'Team 8','weeklyPoints':0})
  row=c['weekly_one']['expected_values'][0];self.assertEqual(row['memberId'],member);self.assertEqual(row['pointsAwarded'],32);self.assertEqual(row['pointDifferential'],32);self.assertEqual(row['rank'],1);self.assertEqual(row['teamName'],'Team 1')
  self.assertEqual(c['ranks_subset']['expected_values'],[{'memberId':member,'rank':1}])
  for name in ['weekly_unscored','weekly_missing','season_missing','ranks_empty','ranks_unscored','ranks_foreign_week','ranks_missing']:self.assertEqual(c[name]['expected_values'],[])
 def test_only_unordered_families_normalize(self):
  rows=[{'memberId':2},{'memberId':1}]
  self.assertEqual(self.m.normalize_rows('season',rows),list(reversed(rows)));self.assertEqual(self.m.normalize_rows('weekly',rows),rows)
 def test_job_normalization_empty_opens_no_connection(self):
  engine=MagicMock();repo=MagicMock();service=self.m.ScoringReadService(engine,repository=repo)
  self.assertEqual(service.get_weekly_points_for_job(1,[]),[]);engine.connect.assert_not_called();repo.weekly_points.assert_not_called()
  self.assertEqual(service._normalize_weeks([12,1,12,-1]),[1,12])
 def test_bad_sample_count_and_provenance_failure(self):
  with self.assertRaises(AssertionError):self.m.validate_result({'expected_rows':0},{'result':{'rows':0},'client_execute_fetch_ms':{'samples':[1]*4}})
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);mf=p/'current.json';mf.write_text('{"result":"PASS"}');connect=MagicMock()
   with patch.object(self.m.base,'ROOT',p/'missing'):
    with self.assertRaises(FileNotFoundError):self.m.run(p,mf,[100],connect)
   connect.assert_not_called();self.assertEqual(json.loads(mf.read_text())['result'],'FAILED')
if __name__=='__main__':unittest.main()
