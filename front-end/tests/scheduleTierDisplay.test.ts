import assert from "node:assert/strict";
import test from "node:test";
import { getOpponentTierDisplayTone } from "../src/utils/scheduleTierDisplay.ts";

test("uses the backend tone for an applied adjustment", () => {
  assert.equal(getOpponentTierDisplayTone({applied: true, tone: "red"}), "red");
  assert.equal(getOpponentTierDisplayTone({applied: true, tone: "green"}), "green");
});

test("missing or unapplied metadata remains neutral", () => {
  assert.equal(getOpponentTierDisplayTone(), "neutral");
  assert.equal(getOpponentTierDisplayTone({applied: false, tone: "red"}), "neutral");
});

test("upcoming basketball matchups show tier colors before a score exists", () => {
  const upcoming = { applied: false, tone: "neutral" as const, tierGap: 2, minimumTierGap: 2 };
  assert.equal(getOpponentTierDisplayTone(upcoming, 1, 3), "red");
  assert.equal(getOpponentTierDisplayTone(upcoming, 3, 1), "green");
});

test("adjacent basketball tiers and double-owned matchups stay neutral", () => {
  assert.equal(getOpponentTierDisplayTone({ applied: false, tone: "neutral", tierGap: 1, minimumTierGap: 2 }, 1, 2), "neutral");
  assert.equal(getOpponentTierDisplayTone({ applied: false, tone: "neutral", tierGap: null, minimumTierGap: 2 }, 1, 3), "neutral");
});

test("unranked basketball opponents are red even with an adjacent fallback tier", () => {
  const adjacent = { applied: false, tone: "neutral" as const, tierGap: 1, minimumTierGap: 2 };
  assert.equal(getOpponentTierDisplayTone(adjacent, 4, 5, true), "red");
  assert.equal(getOpponentTierDisplayTone({ ...adjacent, applied: true, tone: "green" }, 4, 5, true), "red");
});

test("both owned teams show purple regardless of tiers or scoring metadata", () => {
  assert.equal(getOpponentTierDisplayTone(undefined, 1, 3, false, true), "purple");
  assert.equal(getOpponentTierDisplayTone(undefined, 3, 1, false, true), "purple");
  assert.equal(getOpponentTierDisplayTone({ applied: true, tone: "red" }, 1, 3, true, true), "purple");
});

test("colored matchup explanations describe upcoming scoring and actual results", async () => {
  const { getMatchupHoverExplanation } = await import("../src/utils/scheduleTierDisplay.ts");
  const eligible = { tierGap: 2, minimumTierGap: 2 };
  assert.match(getMatchupHoverExplanation("red", eligible)!, /Winning margins are halved; losing margins are doubled/);
  assert.match(getMatchupHoverExplanation("green", eligible)!, /Winning margins are doubled; losing margins are halved/);
  assert.match(getMatchupHoverExplanation("red", { tierGap: 1, minimumTierGap: 2 })!, /No tier multiplier applies/);
  assert.match(getMatchupHoverExplanation("red", { ...eligible, explanation: "Won by 21 → +11 points." })!, /Won by 21 → \+11 points/);
  assert.match(getMatchupHoverExplanation("purple")!, /own both teams/);
  assert.equal(getMatchupHoverExplanation("neutral"), null);
});
