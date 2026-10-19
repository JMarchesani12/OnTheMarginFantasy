import assert from "node:assert/strict";
import test from "node:test";
import { selectDailyTotals, getTeamGamePointDiff } from "../src/utils/leagueScheduleDailyTotals.ts";

test("uses schedule row totals instead of current-member API totals when viewing another week", () => {
  const totals = selectDailyTotals({
    dateHeaders: [{ key: "2026-09-10", label: "Thu, Sep 10" }],
    todayKey: "2026-09-14",
    activeMemberDailyTotals: { "2026-09-10": 99 },
    isViewingCurrentWeek: false,
    teamRows: [
      {
        cellsByDate: {
          "2026-09-10": [
            {
              memberPointDiff: 14,
            },
          ],
        },
      },
      {
        cellsByDate: {
          "2026-09-10": [
            {
              memberPointDiff: -3,
            },
          ],
        },
      },
    ],
  });

  assert.deepEqual(totals, { "2026-09-10": 11 });
});

test("uses API daily totals for the current week", () => {
  const totals = selectDailyTotals({
    dateHeaders: [{ key: "2026-09-10", label: "Thu, Sep 10" }],
    todayKey: "2026-09-14",
    activeMemberDailyTotals: { "2026-09-10": 99 },
    isViewingCurrentWeek: true,
    teamRows: [
      {
        cellsByDate: {
          "2026-09-10": [
            {
              memberPointDiff: 14,
            },
          ],
        },
      },
    ],
  });

  assert.deepEqual(totals, { "2026-09-10": 99 });
});

test("shows opposing team margins for double-owned games while daily totals stay zero", () => {
  const game = { ownsHome: true, ownsAway: true, homeScore: 40, awayScore: 13, memberPointDiff: 0 };
  const home = getTeamGamePointDiff(game, true);
  const away = getTeamGamePointDiff(game, false);
  assert.equal(home, 27);
  assert.equal(away, -27);
  assert.equal(game.memberPointDiff, 0);
  assert.deepEqual(selectDailyTotals({
    dateHeaders: [{ key: "2026-09-10", label: "Thu" }],
    todayKey: "2026-09-14", activeMemberDailyTotals: {}, isViewingCurrentWeek: false,
    teamRows: [
      { cellsByDate: { "2026-09-10": [{ memberPointDiff: home }] } },
      { cellsByDate: { "2026-09-10": [{ memberPointDiff: away }] } },
    ],
  }), { "2026-09-10": 0 });
});

test("keeps backend tier-adjusted margins for games with one owned team", () => {
  assert.equal(getTeamGamePointDiff({ ownsHome: true, ownsAway: false, homeScore: 40, awayScore: 19, memberPointDiff: 11 }, true), 11);
  assert.equal(getTeamGamePointDiff({ ownsHome: false, ownsAway: true, homeScore: 40, awayScore: 19, memberPointDiff: -11 }, false), -11);
});

test("double-owned away wins and ties show correct team margins", () => {
  const game = { ownsHome: true, ownsAway: true, homeScore: 13, awayScore: 40, memberPointDiff: 0 };
  assert.equal(getTeamGamePointDiff(game, true), -27);
  assert.equal(getTeamGamePointDiff(game, false), 27);
  assert.equal(getTeamGamePointDiff({ ...game, homeScore: 40 }, false), 0);
});
