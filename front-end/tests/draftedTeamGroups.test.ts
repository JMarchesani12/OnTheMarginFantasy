import assert from "node:assert/strict";
import test from "node:test";
import { groupDraftedTeams } from "../src/utils/draftedTeamGroups.ts";
const picks = [
  { overallPickNumber: 12, roundNumber: 2, conferenceName: "SEC" },
  { overallPickNumber: 2, roundNumber: 1, conferenceName: "ACC" },
  { overallPickNumber: 1, roundNumber: 1, conferenceName: "SEC" },
  { overallPickNumber: 3, roundNumber: 1, conferenceName: null },
];
test("conference groups retain overall pick order without mutating input", () => {
  const groups = groupDraftedTeams(picks, "conference");
  assert.deepEqual(groups.map((g) => g.label), ["ACC", "Independent", "SEC"]);
  assert.deepEqual(groups[2].picks.map((p) => p.overallPickNumber), [1, 12]);
  assert.equal(picks[0].overallPickNumber, 12);
});
test("rounds sort numerically and preserve overall pick numbers", () => {
  const groups = groupDraftedTeams([...picks, { overallPickNumber: 99, roundNumber: 10, conferenceName: "SEC" }], "round");
  assert.deepEqual(groups.map((g) => g.label), ["Round 1", "Round 2", "Round 10"]);
  assert.deepEqual(groups[0].picks.map((p) => p.overallPickNumber), [1, 2, 3]);
  assert.deepEqual(groupDraftedTeams([], "round"), []);
});
