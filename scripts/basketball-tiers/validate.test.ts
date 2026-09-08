import test from "node:test";
import assert from "node:assert/strict";

import { validateVsConferenceSymmetry } from "./validate.ts";
import type { StatLine } from "./types.ts";

test("validateVsConferenceSymmetry reports mismatched paired records", () => {
  const stats = new Map<string, Map<string, StatLine>>();
  stats.set("SEC", new Map([
    ["Big Ten", {
      conference: "SEC",
      opponent: "Big Ten",
      wins: 3,
      losses: 1,
      games: 4,
      pointsFor: 300,
      pointsAgainst: 280,
      totalMargin: 20,
      winPercentage: 0.75,
      averageMargin: 5,
    }],
  ]));
  stats.set("Big Ten", new Map([
    ["SEC", {
      conference: "Big Ten",
      opponent: "SEC",
      wins: 2,
      losses: 3,
      games: 5,
      pointsFor: 280,
      pointsAgainst: 300,
      totalMargin: -20,
      winPercentage: 0.4,
      averageMargin: -4,
    }],
  ]));

  assert.deepEqual(validateVsConferenceSymmetry(stats), [
    "SEC vs Big Ten games mismatch: 4 !== 5",
    "SEC vs Big Ten wins/losses mismatch: 3-1 !== inverse 3-2",
    "SEC vs Big Ten average margin mismatch: 5 !== inverse 4",
  ]);
});
