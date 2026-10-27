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
