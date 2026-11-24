import unittest
from endpoints.scoring.rules import conference_placement_bonus, national_playoff_bonus

class SeasonBonusRulesTests(unittest.TestCase):
    def test_per_team_awards_sum_into_manager_points(self):
        placements={10:{'rank':1,'bottomRank':10},11:{'rank':2,'bottomRank':9},12:{'rank':10,'bottomRank':1}}
        owned={1:[10,11,12],2:[]}
        positives=conference_placement_bonus(placements,owned,{'first':1.5,'second':1,'third':0.5})
        negatives=conference_placement_bonus(placements,owned,{'last':-1.5},bottom=True)
        self.assertEqual(positives,{1:2.5,2:0});self.assertEqual(negatives,{1:-1.5,2:0})
        self.assertEqual(positives[1]+negatives[1],1)

    def test_shared_conference_positions_get_full_configured_award(self):
        self.assertEqual(conference_placement_bonus({10:{'rank':1},11:{'rank':1}}, {1:[10],2:[11]}, {'first':1.5}),{1:1.5,2:1.5})

    def test_national_tournaments_award_separately_once_per_manager(self):
        depths={'NCAA_TOURNEY':{1:6,2:6,3:0},'FCS_PLAYOFFS':{1:4,2:2,3:1},'FBS_PLAYOFFS':{1:1,2:1,3:5},'NIT':{1:9,2:0,3:0}}
        self.assertEqual(national_playoff_bonus(depths,[1,2,3],3),{1:6,2:3,3:3})

    def test_nonparticipant_gets_no_playoff_award(self):
        self.assertEqual(national_playoff_bonus({'NCAA_TOURNEY':{1:0,2:0}},[1,2],3),{1:0,2:0})
