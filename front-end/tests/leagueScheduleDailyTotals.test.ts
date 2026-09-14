import assert from "node:assert/strict";
import test from "node:test";
import { selectDailyTotals } from "../src/utils/leagueScheduleDailyTotals.ts";

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
