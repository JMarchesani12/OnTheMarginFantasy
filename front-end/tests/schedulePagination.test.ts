import assert from "node:assert/strict";
import test from "node:test";
import { buildSchedulePages, getSchedulePageIndex, moveSchedulePage } from "../src/utils/schedulePagination.ts";
import { buildDateHeadersFromWeek } from "../src/utils/scheduleTable.ts";

test("football Tuesday through Monday stays on one page and advances to the next scoring week", () => {
  const pages = buildSchedulePages(buildDateHeadersFromWeek("2026-10-27T05:00:00Z", "2026-11-03T05:59:59.999Z", "America/Chicago"));
  assert.deepEqual(pages.map(page => [page[0].key, page.at(-1)?.key]), [
    ["2026-10-27", "2026-11-02"],
  ]);
  assert.equal(pages[0].length, 7);
  assert.equal(getSchedulePageIndex(pages, null, "2026-11-02"), 0);
  assert.deepEqual(moveSchedulePage(9, 0, pages.length, 1, 1, 20), { weekNumber: 10, pageIndex: 0 });
});

test("opening dates paginate without advancing the scoring week", () => {
  const pages = buildSchedulePages(buildDateHeadersFromWeek("2026-10-26T00:00:00Z", "2026-11-08T23:59:59Z"));
  assert.deepEqual(pages.map(page => [page[0].key, page.at(-1)?.key]), [
    ["2026-10-26", "2026-11-01"], ["2026-11-02", "2026-11-08"],
  ]);
  assert.deepEqual(moveSchedulePage(1, 0, 2, 1, 1, 20), { weekNumber: 1, pageIndex: 1 });
  assert.deepEqual(moveSchedulePage(1, 1, 2, 1, 1, 20), { weekNumber: 2, pageIndex: 0 });
  assert.deepEqual(moveSchedulePage(2, 0, 1, -1, 1, 20), { weekNumber: 1, pageIndex: -1 });
  assert.equal(getSchedulePageIndex(pages, -1, "2026-10-26"), 1);
});

test("tournament pages follow Monday through Sunday with partial opening and closing pages", () => {
  const pages = buildSchedulePages(buildDateHeadersFromWeek("2027-03-16T00:00:00Z", "2027-04-06T23:59:59Z"));
  assert.deepEqual(pages.map(page => [page[0].key, page.at(-1)?.key]), [
    ["2027-03-16", "2027-03-21"], ["2027-03-22", "2027-03-28"],
    ["2027-03-29", "2027-04-04"], ["2027-04-05", "2027-04-06"],
  ]);
  assert.deepEqual(moveSchedulePage(20, 2, 4, 1, 1, 20), { weekNumber: 20, pageIndex: 3 });
  assert.deepEqual(moveSchedulePage(20, 3, 4, 1, 1, 20), { weekNumber: 20, pageIndex: 3 });
});

test("initial page contains today and navigation respects the first period", () => {
  const pages = buildSchedulePages(buildDateHeadersFromWeek("2026-10-26T00:00:00Z", "2026-11-08T23:59:59Z"));
  assert.equal(getSchedulePageIndex(pages, null, "2026-11-05"), 1);
  assert.equal(getSchedulePageIndex(pages, null, "2026-10-01"), 0);
  assert.deepEqual(moveSchedulePage(1, 0, 2, -1, 1), { weekNumber: 1, pageIndex: 0 });
  assert.deepEqual(moveSchedulePage(1, 1, 2, -1, 1), { weekNumber: 1, pageIndex: 0 });
});

test("league-local boundaries include November 1 without an extra November 9 column", () => {
  const headers = buildDateHeadersFromWeek("2026-10-26T05:00:00Z", "2026-11-09T05:59:59.999Z", "America/Chicago");
  const pages = buildSchedulePages(headers);
  assert.equal(headers.length, 14);
  assert.equal(pages[0].at(-1)?.key, "2026-11-01");
  assert.equal(pages[1].at(-1)?.key, "2026-11-08");
});
