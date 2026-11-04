# Priority 4 continuation

User selected the recommended conflict approach on 2026-11-03 and authorized proceeding. Continue inline in the audit checkout, preserving the previous checkout preference. No push, merge, deployment, configured database access, new infrastructure or dependency installation.

## MOD-025

Require a nonempty exact permutation of current league member IDs, rejecting malformed, duplicate, missing and foreign IDs before writes. Lock an existing DraftState before League, matching live picks/finalization. When state is absent, lock League to serialize first-start/order, then recheck state without taking a new state lock while holding League. A state that appeared during the wait causes conflict. Start is allowed only for Pre-Draft leagues with absent or pristine pre state and no existing picks/turns. Existing persisted state other than an explicitly unstarted state fails closed. A repeated start returns HTTP 409 with code draft_start_conflict and changes no state, picks, turns, timers or events. Resume remains the separate supported path. Validate member count and orders 1..numPlayers before seeding. Keep authorization, transaction ownership, snapshots and acquisition-week defaults.

Alternatives: successful no-op replay would hide accidental lifecycle commands; resetting is unsafe for committed picks. Selected: explicit conflict. League locking covers absent DraftState and concurrent start/order commands. Native PostgreSQL verification covers actual lock waits, including finalization versus start/order; SQLite alone establishes no concurrency claim. Admission serialization remains MOD-012.

## MOD-019

Two independent slices: safe error mapping, then finite request limits. Preserve deliberate authorization concealment and existing success bodies. Normalize REST errors with code/message/requestId while retaining legacy message/error compatibility where consumers require it. Never expose SQL/driver/private exception details. Invalid JSON and SQLAlchemy integrity failures receive deliberate client responses. Preserve framework headers and auth-only recovery codes. Bound request bytes and supplied collections/query values before expensive work; document concrete limits after inventory. No new rate-limiter infrastructure or unverified gateway policy.

## Already implemented

MOD-034 explicit startup and MOD-028A bounded auth refresh retain existing regressions. Broader gateway quotas/production startup and PostgreSQL concurrency evidence stay explicit limitations unless verified locally without configuration.

## Concrete local resource contract

These are operational ceilings, not newly asserted domain maximums: 262144 request bytes (256 KiB), 8192 query-string bytes, 128 scoring week entries and 256 team IDs per trade side. The current scoring requests are season/week collections and trade requests are owner roster selections; these generous ceilings avoid silent truncation and leave empty/duplicate/range semantics with domain policy. No deployed traffic measurements are claimed. Public search permits q up to 128 characters, limit 1..50 (existing service maximum), and offset 0..10000. Larger inputs return 400; excessive body bytes return 413. A terminated unknown-length body is read with a finite one-byte lookahead. Existing complete roster/draft snapshots remain complete.

All Flask errors now use error.code, error.message and requestId, plus a legacy top-level message for browser consumers. Legacy string error codes move into error.code; auth_token_invalid remains reserved for middleware's pre-execution denial. 5xx bodies discard extra fields and use a generic safe message. HTTPException headers are retained; SQLAlchemy IntegrityError maps to 409, DataError to 400. Existing profile-domain error translations remain deliberate. Success bodies/statuses and auth refresh code are unchanged.
