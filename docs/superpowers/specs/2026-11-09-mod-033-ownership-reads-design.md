# MOD-033: shared week-based ownership reads, draft/free-agency pilot

## Intent and scope

Finish the bounded MOD-033 pilot after the approved MOD-033A cap-policy correction. Consolidate repeated week-based ownership existence checks and conference counts across live draft and free-agency submission/application. Preserve behavior, result contracts, acquisition timing and caller lock/transaction boundaries. This is a project with one shared read boundary and two domain consumers, not a migration of every ownership query.

The user explicitly prioritized cap correction first and then requested this extraction. The cap contract is now zero=no teams, positive=inclusive maximum, and negative/missing/invalid=configuration error. MOD-033A's validator and guards remain authoritative and unchanged.

## Approaches and proposed boundary

Use a small connection-aware `api/utils/ownership_reads.py` module, called through existing repository methods. This fits the established service/repository boundaries and preserves injected repository/service override contracts. Moving policy into a global ownership snapshot/service would enlarge the scope and risk caching stale data between drop and add. Calling new helpers directly from services would bypass repository injection and require unnecessary interface changes. Repository delegation is the viable approach under this behavior-preserving scope.

Builder call: preserve the existing repository signatures and SQLAlchemy result shapes, including fetchone/mappings/fetchall behavior, and normalize bound parameter names inside adapters if useful. Do not expose an engine, acquire a connection, open a transaction, lock, write, or commit in the shared module. It may import SQLAlchemy text and the existing effective conference SQL helper, but no endpoint services, configured runtime, jobs, actors or transports.

## Current source and exact consumers

Draft repository methods `live_team_ownership` and `manual_team_ownership` execute identical global league/team/week existence queries. `member_conference_count` is used by the existing live/manual conference-cap service helper. Its SQL counts DISTINCT sportTeamId in one conference and returns a scalar cnt row, including zero.

Transaction workflow repository methods `team_owned` and `member_team_owned` implement free-agent availability/drop-ownership checks. `member_conference_counts` returns grouped conference/count rows for free-agent planning and queued application. These count active rows rather than distinct teams; an empty roster returns no grouped rows. Queued application counts after actually closing drops on the same connection, which must remain so.

Preserve the named methods and their existing service dispatch. The identical manual-draft ownership wrapper naturally delegates to the same primitive as live draft; this does not enable the disabled manual HTTP route or alter its timing.

Explicitly leave auto-pick's `owned_conference_count`, random availability SQL, and trade repository ownership/count queries with outgoing-team exclusions unchanged. Those require their own equivalence evidence if migrated later. Do not expand this pilot because they look similar.

## Shared query responsibilities

The module supplies focused read helpers for:

1. Existence of an active league/team ownership interval, optionally limited to a member.
2. The draft scalar distinct-team conference count.
3. The free-agency grouped active-row conference counts.

Share the ownership interval and effective conference query construction without turning the module into a general query framework. The builder may choose named scalar/grouped helpers or a small explicit query variant; cardinality and result-shape differences must remain visible rather than accidental defaults. SQL identifiers/fragments are fixed trusted code, with data passed as bound parameters.

All ownership reads use league scope, `acquiredWeek <= requestedWeek`, and `droppedWeek IS NULL OR droppedWeek > requestedWeek`. The member-limited existence read also filters memberId. Keep week0 and caller-provided acquired weeks; do not introduce a new week default or normalize caller timing.

Use the existing `conference_sql` season-first resolution: a league-season membership takes precedence, current/default membership is used only when that season has no row, and an invalid seasonal row cannot fall back and hide configuration errors. Existing service-side required mapping/cap checks continue to fail closed; the shared read itself does not grant an independent/uncapped bucket or add a new configuration policy.

Preserve row cardinality, DISTINCT behavior, zero/empty result shapes, and existing league-existence behavior even on characterized legacy/dirty fixtures. Do not silently fix duplicate/overlap data by deduplicating the free-agent count or switch draft counting to raw rows. SQL may differ structurally but must be equivalent for the characterized inputs. Keep one database read per replaced repository call and preserve statement ordering; no cache, eager shared snapshot, extra membership lookup, or query-reduction claim.

## Locking, writes and compatibility

Service entrypoints keep ownership advisory mutex and row-lock order unchanged. Every new read executes on the exact connection passed into the repository. No new begin/connect calls, hidden engines or independent transaction scopes. SQL errors propagate through existing service/HTTP/job boundaries so the caller can roll back.

Do not move slot inserts, drop closures, DraftState changes, pending reservation logic, deadlines, vetoes or authorization into this read module. Validate-before-write and apply-time revalidation order remain intact. Ordinary cap/configuration errors, success payloads and pending-work behavior retain the MOD-033A contract.

Keep `_apply_trade` and public `apply_trade`: source callers show the former is a low-level transfer delegate, while the latter delegates checked pending application to TransactionService. They are not interchangeable operations merely because their names overlap. Record first-party usage/unknown external usage; do not remove either helper in this pilot.

## Verification

Before editing production queries, characterize the original six repository methods on a shared fixture matrix and record expected results. Cover league/member/team isolation, week0, acquired equality, dropped equality, empty intervals, future acquisition, retained history, zero/empty rosters, season override/default/future-season fallback, missing/invalid-season/cross-sport membership, and duplicate legacy ownership intervals. Explicitly prove draft DISTINCT versus free-agency row-count differences rather than assuming cleaned databases make them identical.

Keep permanent expected-result tests for actual SQL/repository methods, not copied Python counting algorithms. For extraction wiring, write a failing delegation test that observes the shared primitive receiving the identical supplied connection. Then implement minimal delegation and show both the characterized matrix and integration tests pass. Any temporary old-SQL comparison artifact belongs in the ignored plan workspace, not a permanent second implementation.

Run actual live/manual draft and free-agency reservation/application fixtures, including full/zero/invalid caps, drop-before-add, supplied-connection rollback, post-closure failures and half-open history. The existing MOD-033A23 test matrix must remain green. Check the ownership mutex protocol and service bodies byte-identical where possible; repository methods/imports and the new helper should carry this extraction.

Run the full credential-free backend suite, touched-source/import boundary checks and whitespace checks. Prior MOD-029 frontend source/test hashes should remain unchanged. Fresh native PostgreSQL is desirable for query equivalence, but the last read-only availability check found Docker stopped. Do not start daemons or contact configured databases to obtain it. If marked task-owned native PostgreSQL becomes available, use only that guarded harness; otherwise document the native coverage gap and do not claim SQLite proves PostgreSQL locks/RLS/runtime behavior.

Obtain one fresh final review; fix material findings with reproducing tests and full green suite. Record source hashes, actual counts and remaining limits. Preserve existing uncommitted audit work and leave this stage uncommitted/undeployed.

## Completion and follow-ups

The MOD-033 pilot completes when the six repository methods delegate to the shared boundary, the paired-domain matrix matches baseline semantics, and supplied connection/lock/write behavior remains unchanged. Auto-pick/trade-specific query migration, broad service cleanup, alternate helper retirement and any performance work remain separately scoped follow-ups rather than requirements to convert all callers now.
