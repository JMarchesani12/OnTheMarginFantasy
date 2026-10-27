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

test("conference counts include each member once per conference", async () => {
  const { countConferenceDrafters } = await import("../src/utils/draftedTeamGroups.ts");
  const counts = countConferenceDrafters([
    { memberId: 1, conferenceName: "SEC" },
    { memberId: 1, conferenceName: "SEC" },
    { memberId: 2, conferenceName: "SEC" },
    { memberId: 1, conferenceName: "ACC" },
    { memberId: 3, conferenceName: null },
  ]);
  assert.equal(counts.get("SEC"), 2);
  assert.equal(counts.get("ACC"), 1);
  assert.equal(counts.get("Independent"), 1);
  assert.equal(countConferenceDrafters([]).size, 0);
});

test("counts members who filled both conference picks separately", async () => {
  const { countConferenceDrafters } = await import("../src/utils/draftedTeamGroups.ts");
  const picks = [
    { memberId: 1, conferenceName: "SEC" },
    { memberId: 1, conferenceName: "SEC" },
    { memberId: 2, conferenceName: "SEC" },
    { memberId: 3, conferenceName: "SEC" },
    { memberId: 3, conferenceName: "SEC" },
    { memberId: 2, conferenceName: "ACC" },
  ];
  assert.equal(countConferenceDrafters(picks).get("SEC"), 3);
  assert.equal(countConferenceDrafters(picks, 2).get("SEC"), 2);
  assert.equal(countConferenceDrafters(picks, 2).get("ACC"), 0);
});

test("hides a conference only after every member fills their allocation", async () => {
  const { getFilledConferences } = await import("../src/utils/draftedTeamGroups.ts");
  const limits = new Map([["SEC", 2], ["ACC", 1], ["Unlimited", 0]]);
  const picks = [
    { memberId: 1, conferenceName: "SEC" },
    { memberId: 1, conferenceName: "SEC" },
    { memberId: 2, conferenceName: "SEC" },
    { memberId: 1, conferenceName: "ACC" },
    { memberId: 2, conferenceName: "ACC" },
  ];
  assert.deepEqual([...getFilledConferences(picks, [1, 2], limits)], ["ACC"]);
  assert.deepEqual([...getFilledConferences([...picks, { memberId: 2, conferenceName: "SEC" }], [1, 2], limits)], ["SEC", "ACC"]);
  assert.equal(getFilledConferences(picks, [], limits).size, 0);
  assert.equal(getFilledConferences(picks, [1, 2, 3], limits).size, 0);
});
