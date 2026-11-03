# MOD-003C current checklist

Updated 2026-10-29. Complete in bounded application/HTTP authorization scope; stopped after final scoring/operational slice. MOD-003B remains complete.

## Completed slices

- [x] POST `/api/roster/memberTeams`: resolve verified principal; reuse `LeagueModel._league_read_scope` for member/commissioner full reads; require target member to belong to requested league. Return indistinguishable 404 for missing/inaccessible league/member before week/roster reads. Validate JSON/integers, translate identity failures, return safe operational errors.
- [x] Recheck caller entitlement and target membership in the final roster query. Late removal returns no rows; no general concurrent-revocation guarantee claimed.
- [x] Preserve same-league other-member reads used by trade selection, commissioner-without-membership access, response fields, locked-week forwarding and context-free trusted model calls. Optional model `reader_user_id=None` remains the trusted boundary; HTTP always passes verified identity. Client actor/job fields cannot bypass it.

- [x] POST `/api/roster/availableTeams`: verified principal and existing member/commissioner full-read policy in initial league lookup and final availability query. Missing/inaccessible leagues return 404 before week/team reads; discoverability and client actor/job fields do not grant access. Direct trusted model calls remain context-free.
- [x] Extracted `utils.requestValidation.integer_field(data, field)` and reused it in both roster routes. Rejects booleans/floats/containers/null/missing/noninteger text; preserves integer-string compatibility. Draft contains similar local validators, deliberately not migrated because MOD-003B is closed. No new authorization policy abstraction needed: both roster methods reuse the established league read-scope helper.

- [x] Free-agency add/drop: verified principal owns the acting member in the URL league. Reuses `integer_field`; new `utils.authorization.require_owned_league_member` checks ownership before domain reads, at transaction entry and before commit. Missing/foreign member/league gets uniform 404, including commissioner impersonation; client job/actor flags cannot grant access. Late ownership loss rolls back pending insertion. Trusted calls omit optional `acting_user_id` and retain original domain rules. Operational failures return safe JSON without SQL details.

- [x] Trade proposal: verified principal must own `fromMemberId` in URL league; reuses `require_owned_league_member` before domain reads, at transaction entry and before commit. Foreign/missing proposer gets uniform 404; late loss rolls back insertion. Existing target/week/team/deadline/conference validation and trusted model calls retained. Both scalar and integer-array input validators share `_integer_value`; malformed arrays cannot masquerade as valid team selections. Safe operational errors.

- [x] Trade response: verified principal owns the receiving member in the URL league; scoped transaction lookup excludes other parties/leagues before domain reads. Existing ACCEPT/REJECT rules retained, including REJECT early-return behavior. Late owner/league/party changes roll back.
- [x] Trade cancellation: verified principal owns the proposing member in the URL league; scoped lookup and late-authority rechecks shared with response. Existing type/PROPOSED cancellation rules retained; trusted calls retain existing party checks. Shared transaction boundary (now `_trade_actor_transaction`) requires actor and league together or neither (trusted); `_trade_action_response` reuses input/error handling for both routes.

- [x] Trade veto: verified principal owns the voter member in URL league and is not a transaction participant. Renamed/generalized shared boundary to `_trade_actor_transaction` with fixed receiving/proposing/voter role predicates; initial and final queries enforce league and voter eligibility. HTTP ineligible participants get 404; trusted model calls retain existing ValueError rules. Vote toggle, settings/status/type eligibility, threshold counting/VETOED behavior and trusted calls unchanged. Late owner/league/participant changes roll back votes and threshold updates.

- [x] Transaction reads (one combined slice): personalized open-trade listing requires verified ownership of requested member in URL league. Pending listing reuses existing member-or-commissioner full league-read policy; discoverability alone does not grant access. Initial checks deny before transaction queries, final SQL rechecks entitlement, trusted model calls retain optional reader-free access. Response fields, personal vote/party grouping, open terminal/type exclusions and pending status filters/order retained.

- [x] Final scoring/operational slice: user explicitly approved internal-only weekly scoring and explicit trade application. POST scoreWeek and POST trade/apply now return 410 (`http_weekly_scoring_disabled`, `http_trade_application_disabled`) without parsing input, resolving application profiles or calling models/persistence; normal JWT middleware still authenticates. No operator role invented.
- [x] Scoring reads: pointsAwarded and scoreSeason use verified principal and existing member-or-commissioner full league-read policy. Shared `league_read_access` guards multi-query reads before work and before returning payloads; optional reader-free model calls retain trusted access. Integer-array validator reused. Scoring/tiebreak/bonus rules unchanged.
- [x] Trusted final-scoreboard dependency: changed its one direct HTTP-handler call to `scoring.scoringModel.compute_end_of_year_season_standings`. Weekly cron already uses the model; transaction apply models unchanged. Actual finalizer function exercised with synthetic in-memory collaborators and without startup imports; no configured job/scheduler executed.

## Remaining slices

None within the MOD-003C card's bounded application/HTTP scope. No other task started.

The card's scope/exclusions identify implementation work. Acceptance/verification describes outcomes to test across those slices, not extra implementation tasks; feature/evidence/benefit fields are context. Existing full-read league policy supports this slice; discoverability alone grants no roster access. No state-machine, scoring-rule or schema changes are included.

## Checks and unresolved failures

- Prior slices retained in full suite: roster 19/19, free agency 13/13, proposal 11/11, response/cancellation 13/13, veto 11/11, transaction reads 12/12.
- Final red run reproduced cross-user/cross-league scoring read exposure, missing-profile access, late-authority data exposure, malformed input coercion and active HTTP write triggers.
- `python3 api/tests/run_isolated.py test_scoring_authorization.py`: 9/9 pass. Both operational routes deny all authenticated roles/missing profiles/job flags/bodies (including malformed JSON) with 410 and no model/persistence calls; middleware still denies anonymous/invalid/expired tokens. Reads cover legitimate members/commissioner-without-membership, cross-league/nonmember/discoverable denial, spoofed actors, missing/ambiguous identity, strict array validation/string compatibility, persisted score/standings contracts, late revocation, trusted reads and safe operational errors.
- `python3 api/tests/run_isolated.py test_operational_trusted_contract.py`: 2/2 pass. Actual trusted pending trade application updates ownership slots and COMPLETED status; isolated final-scoreboard function uses real model SQL to finalize synthetic leagues/season without HTTP context or startup imports. Existing weekly scoring/tiebreak/rules tests remain green in full suite.
- `python3 api/tests/run_isolated.py`: **345/345 pass**, exit 0. Existing synthetic bootstrap failure-path tests print ERROR messages for unmatched tournaments while passing.
- `git diff --check`: pass. Reviewed final route/model/helper/job dependency changes; no scoring/transaction state-machine rules or schema changed. No frontend changes/checks required for backend-only work.
- SQLite fixtures adapt PostgreSQL-only syntax/JSON/driver values and expanding week binds. This is not deployed PostgreSQL/RLS/locking/concurrency, scheduler, browser or integration verification. Revocation after the final check is unverified. No unresolved test failures. No production, configured engine, app factory, listener, worker, configured job/scheduler or environment-value access. Synthetic function-level finalizer test is the only job-path execution.

## Exact next action

MOD-003C is complete in bounded application/HTTP scope. Stop; do not start another MOD or reopen MOD-003B. Before any subsequent task, select its card explicitly and retain the existing deployed-policy/schema/concurrency limitations. MOD-004/005 and transaction state-machine/scoring concerns remain separate backlog work; no deployment/security-wide completion is claimed.

Scope accounting: slices refined existing MOD-003C items (roster/add-drop/propose/respond/cancel/veto/list/pending/apply/score). The final scoring reads belong to its scoring/read-exposure acceptance scope; the one-line finalizer change is a concrete trusted-caller dependency. No independent scope was added.
