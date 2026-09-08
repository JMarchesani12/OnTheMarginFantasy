import test from "node:test";
import assert from "node:assert/strict";

import {
  createConferenceResolver,
  normalizeConferenceName,
  normalizeTeamNameForMatch,
} from "./conferences.ts";
import type { EspnTeamInfo, ConferenceOverrides } from "./types.ts";

const teams: EspnTeamInfo[] = [
  { id: "55", displayName: "Jacksonville State Gamecocks", shortDisplayName: "Jax State", abbreviation: "JVST", conference: "Conference USA" },
  { id: "66", displayName: "Sam Houston Bearkats", shortDisplayName: "Sam Houston", abbreviation: "SHSU", conference: "Conference USA" },
  { id: "77", displayName: "Duke Blue Devils", shortDisplayName: "Duke", abbreviation: "DUKE", conference: "ACC" },
];

const overrides: ConferenceOverrides = {
  "2022-23": {
    JaxState: "ASUN",
    "Sam Houston": "WAC",
  },
  "2023-24": {
    "Jax State": "CUSA",
  },
};

test("normalizeConferenceName collapses explicit conference name variants", () => {
  assert.equal(normalizeConferenceName("Big Ten Conference"), "Big Ten");
  assert.equal(normalizeConferenceName("Conference USA"), "CUSA");
  assert.equal(normalizeConferenceName("Atlantic 10"), "A10");
});

test("normalizeTeamNameForMatch removes mascots and punctuation without fuzzy matching", () => {
  assert.equal(normalizeTeamNameForMatch("Jacksonville State Gamecocks"), "jax state");
  assert.equal(normalizeTeamNameForMatch("St. Thomas (MN) Tommies"), "st thomas");
});

test("createConferenceResolver applies season overrides before ESPN conference data", () => {
  const resolver = createConferenceResolver(overrides, teams);

  assert.equal(
    resolver.resolveConference({ season: "2022-23", teamId: "55", espnConference: "Conference USA" }),
    "ASUN",
  );
  assert.equal(
    resolver.resolveConference({ season: "2022-23", teamId: "66", espnConference: "Conference USA" }),
    "WAC",
  );
  assert.equal(
    resolver.resolveConference({ season: "2024-25", teamId: "77", espnConference: "Atlantic Coast Conference" }),
    "ACC",
  );
});

test("createConferenceResolver reports override names that cannot be matched confidently", () => {
  const resolver = createConferenceResolver({ "2025-26": { "Missing School": "NEC" } }, teams);

  assert.deepEqual(resolver.unmatchedOverrides, [
    { season: "2025-26", teamName: "Missing School", conference: "NEC" },
  ]);
});
