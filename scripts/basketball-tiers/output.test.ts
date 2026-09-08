import test from "node:test";
import assert from "node:assert/strict";

import { rowsToCsv } from "./output.ts";

test("rowsToCsv escapes commas, quotes, and null values", () => {
  const csv = rowsToCsv(
    ["conference", "note", "neutral_site"],
    [
      { conference: "A10", note: "won, then \"lost\"", neutral_site: true },
      { conference: "Independent", note: null, neutral_site: null },
    ],
  );

  assert.equal(
    csv,
    'conference,note,neutral_site\nA10,"won, then ""lost""",true\nIndependent,,\n',
  );
});
