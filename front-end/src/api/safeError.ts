export const CREATE_LEAGUE_UNCERTAIN = "Could not confirm whether your league was created. Check your leagues before submitting again.";
export const JOIN_LEAGUE_UNCERTAIN = "Could not confirm whether your join request completed. Check its status before submitting again.";

export const TRANSACTION_UNCERTAIN = "Could not confirm whether the change completed. Refresh your roster, trades and pending transactions before submitting again.";

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
  ["Free agent deadline has passed", "The free-agent deadline has passed."],
  ["Week is locked", "This week is locked. Refresh the roster to check the current week."],
  ["Trade already resolved", "This trade has already been resolved. Refresh your trades to see its status."],
  ["Only PROPOSED trades can be cancelled", "This trade can no longer be cancelled. Refresh your trades to see its status."],
  ["Trade participants cannot veto their own trade", "You cannot veto a trade you participate in."],
  ["Trade veto is not enabled for this league", "Trade veto is not enabled for this league."],
  ["Only receiving member may respond", "You can only respond to trades sent to you."],
  ["Only the proposing member can cancel this trade", "You can only cancel trades you proposed."],
  ["Team name is required.", "Team name is required."],
  ["League name is required.", "League name is required."],
  ["Already a member of this league", "You are already a member of this league."],
]);
const statusMessages = new Map([
  [400, "Check the entered details and try again."],
  [401, "Please sign in again to continue."],
  [403, "You do not have permission to access this resource or perform this action."],
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

export const READ_ERROR = "Could not load the requested data. Refresh to try again.";
export const WRITE_UNCERTAIN = "Could not confirm whether the change completed. Check the current state before submitting again.";

function normalizedError(error: unknown, fallback: string): SafeApiError {
  if (error instanceof SafeApiError) return error;
  if ((error as { name?: string } | null)?.name === "AbortError") {
    const cancelled = new SafeApiError(0, undefined, "Request cancelled.");
    cancelled.name = "AbortError";
    return cancelled;
  }
  return new SafeApiError(0, undefined, fallback);
}

/** Gate one existing transport call; never clone, refetch, refresh credentials or replay. */
export async function safeResponse(request: Promise<Response>, fallback: string, allowNotFound = false): Promise<Response> {
  try {
    const response = await request;
    if (!response.ok && !(allowNotFound && response.status === 404)) throw await parseApiError(response, fallback);
    return response;
  } catch (error) { throw normalizedError(error, fallback); }
}

/** Preserve callers' existing JSON shape validation while containing decode diagnostics. */
export async function safeJson<T = any>(response: Response, fallback: string): Promise<T> {
  try { return await response.json() as T; }
  catch (error) { throw normalizedError(error, fallback); }
}
