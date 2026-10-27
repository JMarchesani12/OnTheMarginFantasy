import assert from "node:assert/strict";
import test from "node:test";
import { buildDateHeadersFromWeek } from "../src/utils/scheduleTable.ts";

test("opening week includes November 1 and the following full week", () => {
  const headers = buildDateHeadersFromWeek("2026-11-01T00:00:00Z", "2026-11-08T23:59:59Z");
  assert.equal(headers.length, 8);
  assert.equal(headers[0].key, "2026-11-01");
  assert.equal(headers.at(-1)?.key, "2026-11-08");
});

test("tournament scoring period displays every day across calendar weeks", () => {
  const headers = buildDateHeadersFromWeek("2027-03-16T00:00:00Z", "2027-04-06T23:59:59Z");
  assert.equal(headers.length, 22);
  assert.equal(headers.at(-1)?.key, "2027-04-06");
});

test("normal scoring weeks still display seven days", () => {
  assert.equal(buildDateHeadersFromWeek("2026-11-09T00:00:00Z", "2026-11-15T23:59:59Z").length, 7);
});
