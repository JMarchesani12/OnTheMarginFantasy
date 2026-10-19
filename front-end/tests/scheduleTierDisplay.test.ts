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
