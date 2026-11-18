# MOD-028B: safe create/join error pilot

## Intent and chosen approach

The user selected a create/join pilot using known safe messages and status-based fallbacks, preserving input and suppressing arbitrary server text. MOD-028A authentication refresh is already complete and remains unchanged. This pilot establishes the reusable parser and verifies two forms; it does not mark every frontend error consumer migrated.

Choose a small shared API-error helper and explicitly migrate createLeague/requestToJoinLeague plus their CreateLeague/Discover form catches. Broad replacement of every error parser would couple unrelated workflows and exceed this first batch. Blindly displaying JSON message/error strings cannot guarantee private details stay hidden. Known-code/message mapping plus fixed fallbacks gives useful bounded feedback.

## Parser and trust contract

Use the existing MOD-019 HTTP status and structured error.code/error.message envelope; tolerate legacy top-level message and string error. Parse the body once, defensively, without throwing JSON/shape failures into the form. Plaintext, HTML, empty, malformed JSON, arrays, nonstring fields and body-read errors fall back to fixed safe messages. Never render/log/retain arbitrary raw bodies, traceback/SQL/provider text, statusText or unknown exception messages as user feedback. Do not use pattern stripping as a substitute for an allowlist.

Produce a typed safe error carrying numeric HTTP status, an optional recognized machine code, and a client-owned display message. Use status as the semantic boundary:401/403 and5xx cannot be overridden by a field message from an inconsistent body. Recognized codes may refine wording only consistently with their status. Preserve unknown codes only by ignoring them; do not expose raw unknown strings.

For400 validation failures, map exact known create/join business messages to client-owned wording, initially “Team name is required.”, “League name is required.” and “Already a member of this league” (the latter to “You are already a member of this league.”). Do not echo dynamic field lists/identifiers/configuration or unknown validation strings. Generic400 instructs checking entered details;401 asks signing in again;403 states permission denied;404/410 state unavailable;409 asks refreshing/checking current state;413 reports oversized request;415 reports unsupported request format;429 asks waiting before another attempt. Other4xx use an action-specific safe fallback. No automatic retries.

For5xx or a transport/unknown thrown error, avoid claiming the mutation failed definitively: the operation may have committed. Use fixed action-specific wording telling users completion could not be confirmed and to check their leagues/request status before submitting again. Keep the distinction between HTTP rejection and an unknown transport outcome. The builder owns concise final wording and exact helper/class names, with tests pinning behavior rather than broad message heuristics.

Provide a UI formatter that accepts only this typed/trusted safe error as display authority and otherwise returns the caller's fixed uncertainty message. Other fetch/SDK/network exceptions must not leak their message. Do not add credentials, private payloads or raw diagnostics to the error object or console output. Correlation-ID UI/logging and generic resource budgets are outside this pilot.

## Consumer behavior and boundaries

Only createLeague/requestToJoinLeague HTTP failure branches adopt the parser. Successful payloads, URLs, methods, request bodies and public function signatures remain unchanged. No response clone/replay, generic fetch wrapper, SDK/auth refresh, backend envelope/status/schema or admission timing change. Preserve the typed status semantics used by other APIs; no migration of preview/user/draft/transaction errors in this batch.

CreateLeague removes the generic “check console/backend logs” feedback and raw console logging of the mutation exception. Both forms retain current typed values on rejection/uncertainty, return from submitting state and permit deliberate correction/retry. Keep native form validation, field-error associations, existing preview/account/route guards and successful navigation/status behavior. Read-retry and mutation-retry must remain separate; no effect or catch automatically resends a write. Join's existing server idempotence is not a reason to replay a request in the browser.

## Verification and completion

Test the helper with actual Response objects for nested/legacy messages and codes, status/body mismatches, unknown/malicious message/error/details/statusText, JSON/non-JSON/empty/malformed/read failure, and every supported status class. Assert safe numeric status/code, no raw text retained, and no extra fetch/body read/retry. Test the actual two API helpers with controlled transport and their actual form consumers: retain inputs/re-enable submit for JSON message/error/plaintext/empty/server/network failures, show safe actionable feedback, and keep one write per deliberate submit. Preserve successful payload/navigation and MOD-026–029 context regressions.

Run full frontend tests, production build, import graph and diff checks; obtain one fresh final review and fix material findings with RED→GREEN/full green. Record exact commands, hashes, decisions and limits. Controlled hooks/transport do not prove browser/live-provider behavior. No live services, dependency installation or backend/database work required; preserve existing working changes, leave this pilot uncommitted/undeployed. Remaining consumer batches stay explicitly open under MOD-028B.
