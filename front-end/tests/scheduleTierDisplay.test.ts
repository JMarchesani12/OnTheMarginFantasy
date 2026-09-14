import assert from "node:assert/strict";
import test from "node:test";
import { getOpponentTierDisplayTone } from "../src/utils/scheduleTierDisplay.ts";

test("marks a lower-tier football opponent red", () => {
  assert.equal(
    getOpponentTierDisplayTone({
      sportId: 2,
      ownedTeamTier: 1,
      opponentTeamTier: 2,
    }),
    "red",
  );
});

test("marks a higher-tier football opponent green", () => {
  assert.equal(
    getOpponentTierDisplayTone({
      sportId: 2,
      ownedTeamTier: 2,
      opponentTeamTier: 1,
    }),
    "green",
  );
});

test("keeps a one-tier basketball gap neutral", () => {
  assert.equal(
    getOpponentTierDisplayTone({
      sportId: 1,
      ownedTeamTier: 2,
      opponentTeamTier: 1,
    }),
    "neutral",
  );
});

test("marks a two-tier basketball gap red or green", () => {
  assert.equal(
    getOpponentTierDisplayTone({
      sportId: 1,
      ownedTeamTier: 1,
      opponentTeamTier: 3,
    }),
    "red",
  );
  assert.equal(
    getOpponentTierDisplayTone({
      sportId: 1,
      ownedTeamTier: 3,
      opponentTeamTier: 1,
    }),
    "green",
  );
});
