import copy
import json
from pathlib import Path
import unittest
from endpoints.scoring.standings_provider import parse_conference_standings, ESPNStandingsProvider, provider_year

FIXTURES = Path(__file__).parent / 'fixtures' / 'standings'

class StandingsProviderTests(unittest.TestCase):
    def payload(self, sport='football'):
        return json.loads((FIXTURES / f'{sport}-big12.json').read_text())

    def test_uses_explicit_conference_positions_not_response_order(self):
        data = self.payload(); data['children'][0]['standings']['entries'].reverse()
        conf = parse_conference_standings(data, 2025, 80)[0]
        self.assertEqual(conf['status'], 'ready')
        tech = next(e for e in conf['entries'] if e['externalId'] == '2641')
        self.assertEqual((tech['rank'], tech['bottomRank'], tech['record']), (1, 15, '8-1'))

    def test_basketball_maps_ending_year_from_regular_season_end(self):
        self.assertEqual(provider_year('basketball/mens-college-basketball', '2027-03-07'), 2027)
        conf = parse_conference_standings(self.payload('basketball'), 2026, 50)[0]
        arizona = next(e for e in conf['entries'] if e['externalId'] == '12')
        self.assertEqual(arizona['rank'], 1)

    def test_rejects_wrong_year_and_fbs_response_for_fcs(self):
        for year,group in [(2026,80),(2025,81)]:
            with self.assertRaises(ValueError): parse_conference_standings(self.payload(),year,group)
        data=self.payload();data['children'][0]['standings']['seasonType']=3
        with self.assertRaises(ValueError): parse_conference_standings(data,2025,80)

    def test_missing_conference_record_cannot_be_guessed_from_seed_or_national_rank(self):
        data=self.payload(); entry=data['children'][0]['standings']['entries'][0]
        entry['stats']=[s for s in entry['stats'] if s['type']!='vsconf'];entry['team']['rank']=1
        self.assertEqual(parse_conference_standings(data,2025,80)[0]['status'],'pending')

    def test_division_and_independent_positions_are_not_conference_positions(self):
        for name,is_conf in [('Sun Belt - East',False),('Unverified division',False)]:
            data=self.payload(); c=data['children'][0];c['name']=name;c['isConference']=is_conf
            self.assertEqual(parse_conference_standings(data,2025,80)[0]['status'],'pending')

    def test_duplicate_team_and_invalid_conference_record_are_rejected(self):
        data=self.payload(); entries=data['children'][0]['standings']['entries']
        entries[1]['team']['id']=entries[0]['team']['id']
        self.assertEqual(parse_conference_standings(data,2025,80)[0]['status'],'pending')
        data=self.payload();stats=data['children'][0]['standings']['entries'][0]['stats']
        next(s for s in stats if s['type']=='vsconf')['summary']='0-0'
        self.assertEqual(parse_conference_standings(data,2025,80)[0]['status'],'pending')

    def test_tied_published_conference_records_share_position_regardless_of_seed(self):
        result=parse_conference_standings(self.payload('basketball'),2026,50)[0]
        records=[e for e in result['entries'] if e['record']=='12-6']
        self.assertEqual(len(records),3)
        self.assertEqual([e['rank'] for e in records],[3,3,3])

    def test_fetch_uses_singular_group_and_propagates_provider_failure(self):
        calls=[]
        class Response:
            def raise_for_status(self): pass
            def json(self): return {'ok':True}
        def get(url,**kwargs): calls.append((url,kwargs));return Response()
        self.assertEqual(ESPNStandingsProvider(get=get).fetch('football/college-football',2025,81),{'ok':True})
        self.assertEqual(calls[0][1]['params'],{'season':2025,'seasontype':2,'level':3,'group':81})
        def fail(*args,**kwargs): raise RuntimeError('provider down')
        with self.assertRaises(RuntimeError): ESPNStandingsProvider(get=fail).fetch('football/college-football',2025,81)

    def test_nested_divisions_use_conference_records_not_division_seeds(self):
        data=self.payload();base=data['children'][0];entries=base['standings']['entries']
        data['children']=[{'id':'37','name':'Sun Belt Conference','isConference':True,'children':[
            {'id':'167','name':'Sun Belt - East','isConference':False,'standings':{**base['standings'],'entries':entries[:8]}},
            {'id':'168','name':'Sun Belt - West','isConference':False,'standings':{**base['standings'],'entries':entries[8:]}}]}]
        result=parse_conference_standings(data,2025,80)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['status'],'ready');self.assertEqual(len(result[0]['entries']),16)

    def test_known_independent_group_has_no_conference_award_not_a_fabricated_rank(self):
        data=self.payload();group=data['children'][0];group['id']='18';group['name']='FBS Independents'
        for entry in group['standings']['entries']: entry['stats']=[]
        result=parse_conference_standings(data,2025,80)[0]
        self.assertEqual(result['status'],'ready')
        self.assertTrue(all(e['rank'] is None and e['bottomRank'] is None for e in result['entries']))
