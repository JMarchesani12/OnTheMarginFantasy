import assert from "node:assert/strict";
import test from "node:test";
import { feedbackMailto, formatFeedback } from "../src/utils/feedback.ts";

test("bug feedback includes reproduction details and optional expected behavior", () => {
  assert.deepEqual(formatFeedback("bug", " Missing score ", " Open standings ", " A score ", "/leagues/12"), {
    subject: "[On The Margin Fantasy] Bug report: Missing score",
    body: "Open standings\n\nExpected behavior:\nA score\n\nPage: /leagues/12",
  });
});

test("feature feedback omits bug-only fields and page context unless supplied", () => {
  assert.deepEqual(formatFeedback("feature", "Export", "Share standings", "Old bug details", ""), {
    subject: "[On The Margin Fantasy] Feature suggestion: Export", body: "Share standings",
  });
});

test("email draft preserves punctuation and line breaks without introducing email parameters", () => {
  const subject = "Bug & feature? #1";
  const body = "First line\nSecond line &bcc=someone@example.com";
  const params = new URLSearchParams(feedbackMailto("support@example.com", subject, body).split("?")[1]);
  assert.equal(params.get("subject"), subject);
  assert.equal(params.get("body"), body);
  assert.deepEqual([...params.keys()], ["subject", "body"]);
});
