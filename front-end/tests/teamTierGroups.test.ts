import assert from "node:assert/strict";
import test from "node:test";
import { groupTeamsByTier, getTierLabel } from "../src/utils/teamTierGroups.ts";

test("orders tiers numerically and teams alphabetically without mutating input", () => {
  const teams = [
    { teamName: "Zulu", tier: 2 },
    { teamName: "Beta", tier: 1 },
    { teamName: "Alpha", tier: 1 },
    { teamName: "Ten", tier: 10 },
  ];
  assert.deepEqual(groupTeamsByTier(teams).map(g => [g.label, g.teams.map(t => t.teamName)]), [
    ["Tier 1", ["Alpha", "Beta"]], ["Tier 2", ["Zulu"]], ["Tier 10", ["Ten"]],
  ]);
  assert.equal(teams[0].teamName, "Zulu");
});

test("omits tier headings for a single tier or empty list", () => {
  assert.equal(groupTeamsByTier([{ teamName: "Alpha", tier: 1 }])[0].label, null);
  assert.deepEqual(groupTeamsByTier([]), []);
});

test("keeps unknown tiers separate without assigning a fictional tier", () => {
  assert.deepEqual(groupTeamsByTier([
    { teamName: "Unknown" }, { teamName: "Known", tier: 1 },
  ]).map(g => g.label), ["Tier 1", "Unassigned tier"]);
});

test("names football and basketball tiers in order", () => {
  assert.deepEqual([1,2,3].map(tier => getTierLabel(tier, 2)), ["FBS", "FCS", "Tier 3"]);
  assert.deepEqual([1,2,3,4,5].map(tier => getTierLabel(tier, 1)), ["Power", "High Major", "Mid Major", "Low Major", "Play-In Bound"]);
  assert.equal(getTierLabel(2, "College Football"), "FCS");
  assert.equal(getTierLabel(1, "NCAA Men's Basketball"), "Power");
  assert.equal(getTierLabel(1, "1"), "Power");
  assert.equal(getTierLabel(null, 1), "Unassigned tier");
  assert.equal(getTierLabel(6, 1), "Tier 6");
  assert.equal(getTierLabel(1), "Tier 1");
});

test("uses sport labels for multiple groups and keeps single-tier headings hidden", () => {
  assert.deepEqual(groupTeamsByTier([{teamName: "B", tier: 2}, {teamName: "A", tier: 1}], 1).map(g => g.label), ["Power", "High Major"]);
  assert.equal(groupTeamsByTier([{teamName: "A", tier: 1}], 1)[0].label, null);
});

test("orders conferences before team names within each tier", () => {
  const teams = [
    { teamName: "Auburn", conferenceName: "SEC", tier: 1 },
    { teamName: "Wake Forest", conferenceName: "ACC", tier: 1 },
    { teamName: "Duke", conferenceName: "ACC", tier: 1 },
    { teamName: "Army", conferenceName: null, tier: 1 },
    { teamName: "Zeta", conferenceName: "ACC", tier: 2 },
  ];
  assert.deepEqual(groupTeamsByTier(teams, 1).map(group => group.teams.map(team => team.teamName)), [
    ["Duke", "Wake Forest", "Army", "Auburn"], ["Zeta"],
  ]);
  assert.equal(teams[0].teamName, "Auburn");
});
