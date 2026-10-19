import assert from "node:assert/strict";
import test from "node:test";
import { groupTeamsByTier } from "../src/utils/teamTierGroups.ts";

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
