export type FeedbackCategory = "bug" | "feature";

export function formatFeedback(category: FeedbackCategory, title: string, details: string, expected: string, page: string) {
  const subject = `[On The Margin Fantasy] ${category === "bug" ? "Bug report" : "Feature suggestion"}: ${title.trim()}`;
  const body = [details.trim(),
    category === "bug" && expected.trim() ? `Expected behavior:\n${expected.trim()}` : "",
    page ? `Page: ${page}` : ""].filter(Boolean).join("\n\n");
  return { subject, body };
}

export function feedbackMailto(email: string, subject: string, body: string) {
  return `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}
