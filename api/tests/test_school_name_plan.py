"""Short canonical names use provider-school identity and preserve ambiguity."""
import unittest
from utils.school_names import plan_school_names


class SchoolNamePlanTests(unittest.TestCase):
    def test_maps_provider_id_to_real_school_id_and_keeps_unmapped_school(self):
        plan=plan_school_names([{'id':369,'name':'University of Northern Iowa'},{'id':999,'name':'Unmapped School'}],
            [{'schoolId':369,'externalId':'2460'}],{'groups':[{'id':'2460','label':'Northern Iowa'}]})
        self.assertEqual(plan['updates'],[{'schoolId':369,'oldName':'University of Northern Iowa','newName':'Northern Iowa'}])
        self.assertEqual(plan['unmappedSchoolIds'],[999])

    def test_conflicting_names_for_one_school_block_instead_of_guessing(self):
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            plan_school_names([{'id':1,'name':'School'}],[{'schoolId':1,'externalId':'10'},{'schoolId':1,'externalId':'11'}],
                {'groups':[{'id':'10','label':'School A'},{'id':'11','label':'School B'}]})

    def test_replay_does_not_plan_an_already_canonical_name(self):
        self.assertEqual(plan_school_names([{'id':369,'name':'Northern Iowa'}],[{'schoolId':369,'externalId':'2460'}],
            {'groups':[{'id':'2460','label':'Northern Iowa'}]})['updates'],[])

    def test_one_provider_id_cannot_rename_two_distinct_schools(self):
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            plan_school_names([{'id':1,'name':'First'},{'id':2,'name':'Second'}],
                [{'schoolId':1,'externalId':'10'},{'schoolId':2,'externalId':'10'}],
                {'groups':[{'id':'10','label':'First'}]})

    def test_one_provider_id_shared_by_two_sports_of_same_school_is_valid(self):
        plan=plan_school_names([{'id':369,'name':'University of Northern Iowa'}],
            [{'schoolId':369,'externalId':'2460'},{'schoolId':369,'externalId':'2460'}],
            {'groups':[{'id':'2460','label':'Northern Iowa'}]})
        self.assertEqual(len(plan['updates']),1)
