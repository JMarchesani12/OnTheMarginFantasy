import assert from "node:assert/strict";
import test from "node:test";
import { getLeagueRank } from "../src/utils/leagueDetailCalculations.ts";

test("ranks by descending points and shares ranks for ties", () => {
  const standings = [{ memberId: 1, points: 10 }, { memberId: 2, points: 20 }, { memberId: 3, points: 20 }, { memberId: 4, points: -1 }];
  assert.deepEqual(getLeagueRank(standings, 1), { rank: 3, tied: false });
  assert.deepEqual(getLeagueRank(standings, 2), { rank: 1, tied: true });
  assert.deepEqual(getLeagueRank(standings, 4), { rank: 4, tied: false });
  assert.equal(standings[0].memberId, 1);
});

test("returns no rank when the current member is unavailable", () => {
  assert.equal(getLeagueRank([], 1), null);
  assert.equal(getLeagueRank([{ memberId: 1, points: 0 }], null), null);
  assert.equal(getLeagueRank([{ memberId: 1, points: 0 }], 2), null);
});

test("a solo member ranks first and zero-point ties are shared", () => {
  assert.deepEqual(getLeagueRank([{ memberId: 1, points: 0 }], 1), { rank: 1, tied: false });
  assert.deepEqual(getLeagueRank([{ memberId: 1, points: 0 }, { memberId: 2, points: 0 }], 1), { rank: 1, tied: true });
});
