import importlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
class IngestionMeasureTests(unittest.TestCase):
 def setUp(self):self.m=importlib.import_module('measure_mod022_ingestion')
 def test_existing_path_count_formulas(self):
  for n in [1,4,16]:
   self.assertEqual(self.m.expected_counts(n,'league',1)['sql'],40*n)
   self.assertEqual(self.m.expected_counts(n,'league',2)['upserts'],8*n)
   self.assertEqual(self.m.expected_counts(n,'season',1),{'sql':29,'fetches':2,'upserts':3})
 def test_real_parser_canned_overlap_and_correction(self):
  m=self.m;p=m.Provider();client=m.CannedClient('https://synthetic.invalid','basketball/audit',p)
  raw=client.fetch_scoreboard_for_date('20261115',10);games=[client.extract_game_from_event(e) for e in client.iter_scoreboard_events(raw)]
  self.assertEqual([g['externalGameId'] for g in games if g],['A','B']);self.assertIsNone(games[-1])
  p.revision=1;game=client.extract_game_from_event(client.fetch_scoreboard_for_date('20261115',20)['events'][0]);self.assertEqual(game['homeScore'],99);self.assertEqual(game['broadcast'],'Correction')
  self.assertEqual(p.calls,[('20261115',10),('20261115',20)])
 def test_failure_is_one_shot_and_records_request(self):
  p=self.m.Provider();p.fail_once=True;c=self.m.CannedClient('', '',p)
  with self.assertRaises(OSError):c.fetch_scoreboard_for_date('20261115',20)
  self.assertEqual(len(c.fetch_scoreboard_for_date('20261115',20)['events']),2)
  self.assertEqual(len(p.calls),2)
 def test_classification_and_full_expected_game_values(self):
  self.assertEqual(self.m.classify('INSERT INTO "GameResult" VALUES (1)'),'upsert')
  with self.assertRaises(AssertionError):self.m.classify('SELECT unexpected')
  rows=self.m.expected_games(1);self.assertEqual(len(rows),3);self.assertEqual(rows[0]['homeScore'],99);self.assertEqual(rows[0]['homeTeamId'],1);self.assertEqual(rows[0]['seasonPhaseId'],1)
 def test_provenance_failure_replaces_pass_before_connect(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);mf=p/'current.json';mf.write_text('{"result":"PASS"}');connect=MagicMock()
   with patch.object(self.m.base,'ROOT',p/'missing'):
    with self.assertRaises(FileNotFoundError):self.m.run(p,mf,[1],connect)
   connect.assert_not_called();self.assertEqual(json.loads(mf.read_text())['result'],'FAILED')
if __name__=='__main__':unittest.main()
