export const CREATE_LEAGUE_UNCERTAIN = "Could not confirm whether your league was created. Check your leagues before submitting again.";
export const JOIN_LEAGUE_UNCERTAIN = "Could not confirm whether your join request completed. Check its status before submitting again.";

class SafeApiError extends Error {
  readonly status: number;
  readonly code?: string;
  constructor(status: number, code: string | undefined, message: string) {
    super(message);
    this.name = "SafeApiError";
    this.status = status;
    this.code = code;
  }
}

const codes = new Map<number, readonly string[]>([
  [400, ["request_invalid"]],
  [401, ["authentication_required", "auth_token_missing", "auth_token_invalid"]],
  [403, ["access_denied", "commissioner_identity_mismatch", "user_identity_mismatch"]],
  [404, ["resource_not_found"]], [405, ["method_not_allowed"]],
  [409, ["resource_conflict"]], [410, ["operation_disabled"]],
  [413, ["request_too_large"]], [415, ["media_type_unsupported"]], [429, ["rate_limited"]],
]);
const businessMessages = new Map([
  ["Team name is required.", "Team name is required."],
  ["League name is required.", "League name is required."],
  ["Already a member of this league", "You are already a member of this league."],
]);
const statusMessages = new Map([
  [400, "Check the entered details and try again."],
  [401, "Please sign in again before submitting."],
  [403, "You do not have permission to submit this request."],
  [404, "This resource is unavailable."], [410, "This operation is unavailable."],
  [409, "This request conflicts with the current state. Refresh and check its status before submitting again."],
  [413, "The request is too large. Reduce its size before submitting again."],
  [415, "The request format is unsupported. Reload the page before submitting again."],
  [429, "Too many requests. Wait before trying again."],
]);
function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

/** Consume an unsuccessful response once; arbitrary server text is never display authority. */
export async function parseApiError(response: Response, uncertaintyMessage: string): Promise<Error & { readonly status: number; readonly code?: string }> {
  let payload: Record<string, unknown> | null = null;
  try { payload = record(await response.json()); } catch { /* Non-JSON/read failures use fixed status feedback. */ }
  const structured = record(payload?.error);
  const rawCode = structured?.code ?? (typeof payload?.error === "string" ? payload.error : undefined);
  const allowedCodes = response.status >= 500 ? ["internal_error"] : codes.get(response.status) ?? [];
  const code = typeof rawCode === "string" && allowedCodes.includes(rawCode) ? rawCode : undefined;
  const candidate = structured?.message ?? payload?.message ?? payload?.error;
  const business = response.status === 400 && typeof candidate === "string" ? businessMessages.get(candidate) : undefined;
  const message = response.status >= 500 ? uncertaintyMessage : business ?? statusMessages.get(response.status) ?? uncertaintyMessage;
  return new SafeApiError(response.status, code, message);
}

/** SDK/network exceptions and shape-compatible objects are not trusted error messages. */
export function safeErrorMessage(error: unknown, uncertaintyMessage: string): string {
  return error instanceof SafeApiError ? error.message : uncertaintyMessage;
}
