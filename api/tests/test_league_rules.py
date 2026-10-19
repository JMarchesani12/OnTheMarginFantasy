import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rules.leagueRules import resolve_rules, settings_for_creation, settings_for_update, adjust_margin, describe_rules

class LeagueRulesTests(unittest.TestCase):
    def test_legacy_version_does_not_follow_current_version(self):
        with patch('rules.leagueRules.CURRENT_VERSION', 'future'):
            self.assertEqual(resolve_rules(1, {})['version'], 'v1')

    def test_creation_pins_server_version_and_preserves_input(self):
        settings = {'bonuses': {}}
        self.assertEqual(settings_for_creation(1, settings)['ruleSetVersion'], 'v1')
        self.assertNotIn('ruleSetVersion', settings)
        with self.assertRaises(ValueError):
            settings_for_creation(1, {'ruleSetVersion': 'unknown'})

    def test_updates_preserve_legacy_and_explicit_version(self):
        for existing in [{}, {'ruleSetVersion': 'v1'}]:
            self.assertEqual(settings_for_update(1, existing, {'timezone': 'UTC'})['ruleSetVersion'], 'v1')
            with self.assertRaises(ValueError):
                settings_for_update(1, existing, {'ruleSetVersion': 'v2'})

    def test_invalid_settings_and_explicit_versions_fail(self):
        for settings in [[], 'bad', {'ruleSetVersion': None}, {'ruleSetVersion': 'v2'}]:
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                resolve_rules(1, settings)

    def test_basketball_boundaries_and_fixed_multipliers(self):
        rules = resolve_rules(1, {})
        for a, b, margin, expected in [(1,2,21,21),(2,1,-21,-21),(1,3,21,11),(1,3,-21,-42),(3,1,21,42),(3,1,-21,-11),(1,9,21,11),(9,1,-20,-10)]:
            with self.subTest(a=a,b=b,margin=margin):
                result = adjust_margin(margin,a,b,rules)
                self.assertEqual(result['adjustedMargin'], expected)
                self.assertEqual(result['applied'], abs(a-b)>=2)

    def test_football_and_other_sports_keep_one_tier_threshold(self):
        for sport in [2,3]:
            self.assertEqual(adjust_margin(21,1,2,resolve_rules(sport, {}))['adjustedMargin'],11)

    def test_zero_unknown_and_double_owned_are_not_adjusted(self):
        rules = resolve_rules(1,{})
        for margin,a,b,double in [(0,1,3,False),(21,None,3,False),(21,1,3,True)]:
            result=adjust_margin(margin,a,b,rules,double_owned=double)
            self.assertFalse(result['applied'])
            self.assertEqual(result['tone'],'neutral')
            self.assertEqual(result['adjustedMargin'],0 if double else margin)

    def test_explanations_use_actual_results_and_rules(self):
        rules=resolve_rules(1,{})
        result=adjust_margin(21,1,3,rules)
        self.assertIn('+11',result['explanation'])
        self.assertIn('2 tiers lower',result['explanation'])
        payload=describe_rules(1,{},[])
        self.assertIn('2 or more',payload['summary'])
        self.assertEqual(payload['tierAdjustment']['minimumTierGap'],2)
        self.assertEqual(payload['examples'][0]['adjustedMargin'],11)
