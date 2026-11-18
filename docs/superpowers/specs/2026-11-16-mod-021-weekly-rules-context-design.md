# MOD021 — per-call weekly scoring rules context

## Intent and selected approach

Remove repeated league/rule-resolution reads inside one supplied-connection weekly scoring call. The user selected rules-only context first. Keep the existing scoring algorithm, SQL game/ownership/tier/phase reads, caller transaction and score replacement. Design and implementation plan are this task's deliverables; no product implementation yet.

Approaches considered: (1) a small immutable rules context per supplied-connection call, selected because ScheduleReadService already accepts resolved_rules and this isolates a measured repetition; (2) a complete consistent scoring snapshot, deferred because freezing games/ownership/tiers/phases or changing isolation/locks is a larger concurrency policy. Game batching is a later separately reviewed change, not part of either the first design or its benefit claims.

Continue Python/SQLAlchemy/PostgreSQL and the approved native inline workflow with one final review per implementation batch. User owns commits/integration; no dependency/schema/index/scheduler/provider changes.

## Current behavior and caller inventory

`WeeklyCompletionService.run` owns a transaction and league ownership advisory mutex for each action; `_step` calls `compute_weekly_scores_for_job(...,conn=conn)`. Calendar maintenance also supplies a transaction while rebuilding/rescoring and already owns its established season/ownership/calendar locks. Preserve these boundaries and signatures.

The scorer reads week metadata/final-period guards and members, then calls the schedule service for each member's adjusted game margins. Every default member call loads League and resolves rules; biggest-margin fallback repeats that work. H2H reads use raw home/away scores, not tier-adjusted rules. The Week row lock and atomic delete/insert replacement occur after score computation. With conn supplied all reads/writes reuse it; without conn existing helper-owned transactions remain. HTTP scoring is410 and remains disabled.

Production constructors inject ScheduleReadService. Standalone native verification helpers inject schedule stubs; several unit tests subclass scoring helpers with old signatures. Inventory covers `compute_weekly_scores_for_job`, member-difference/tie helpers, schedule member-game reads, weekly completion/calendar maintenance and audit measure_mod021_weekly. Keep the public scorer's signature/return unchanged. Additions to internal/helper keyword interfaces must be inventoried explicitly; no claim about unknown external Python subclass overrides.

## Context contract

One context belongs to exactly one invocation of `compute_weekly_scores_for_job` with a non-None conn, one league ID and one week number. Create it after existing week/final-period and nonempty-member validation, immediately before the first member-game computation. A rejected week/empty roster must not perform a new rule read or change error precedence.

Read League on that same supplied connection, then call the same resolve_rules(sport,settings) used by current ScheduleReadService. Capture only its resolved scalar rule mapping (version, minimumTierGap, favored win/loss multipliers, rounding, double-owned margin). No mutable settings object, ORM row, game list, roster, tier map or phase data is cached. Freeze a defensive copy; do not store it on the scoring/schedule service, engine, module, thread-local or transaction info. The private context may carry connection identity/league/week solely to reject mismatched internal reuse before schedule queries. It is discarded when the call returns or raises.

Pass the context explicitly through the member-difference and largest-margin fallback paths. ScheduleReadService receives its existing resolved_rules argument and supplied conn. All member/fallback rule-dependent margin calculations in that call use the captured mapping. H2H remains unchanged and must not receive adjusted margins or a new rules query.

Use a named supplied-connection rule-resolution method on ScheduleReadService so the scorer does not couple to its private calendar repository. This method reuses existing _get_league/resolve_rules and opens no transaction. The normal no-context schedule method still resolves rules exactly as before; no public schedule SQL/projection changes.

The no-conn scoring path retains current helper dispatch and reads; it gets no new hidden transaction, context or rules lookup. This keeps existing standalone/subclass behavior outside the explicitly bounded supplied-connection optimization. Do not silently upgrade it to a different isolation/locking contract. It can be designed separately later.

## Mutable-input and locking policy

This is an explicit rule-definition snapshot only, at context creation. If rules source changes later in the same transaction or another transaction, this call retains its captured resolved rules; a new scoring invocation reads them anew, including another week/league using the same connection or a retry after failure. No context is shared across multiple weeks in one calendar-maintenance transaction.

Do not change isolation or acquire new League/SportTeam/SeasonPhase/Week locks. Preserve the existing ownership mutex, late Week lock and caller rollback/commit behavior. Tier assignments/unranked fallback, phase rules, GameResult rows, ownership windows and league-derived schedule SQL context retain their current database statement semantics; under READ COMMITTED later statements may see later committed inputs. No claim of full scoring consistency under concurrent edits. In particular, this is not a historical snapshot or protection against direct league sport/year rewrites; those SQL contexts still behave as before. Normal league updates do not expose sport changes, and rule-version edits already have their own validation policy; do not loosen that policy.

A complete consistent input snapshot or earlier lock is separate work. Do not add either indirectly to make a test deterministic. Native tests deliberately demonstrate the chosen boundary: rules held for the call, tier/phase/game facts still read by unchanged SQL.

## Compatibility and algorithm invariants

Preserve `compute_weekly_scores_for_job(league_id,week_number,conn=None)` and returned/stored fields. Optional private/helper context parameters must not alter default behavior or be passed to old no-conn overrides. Do not use inspect/signature probing, TypeError-catching fallback or instance monkeypatching to hide unsupported adapters. Update owned supplied-connection test doubles to the explicit schedule rules capability and document that requirement.

Keep member-ID base order, raw pair H2H precedence, current nonrecursive tie resolution, largest absolute adjusted margin fallback and waterfall points. Do not cache/reuse member-game results even on fallback, batch pair reads, change tie semantics, infer snapshots for tiers/phases, or optimize inserts. Keep half-open ownership, double-owned zero contribution, basketball unranked treatment and phase multipliers/positive-only behavior.

Final-period end/split guards, week0, week lock/delete/insert scope, existing score replacement, caller connection ownership and failure/commit/rollback behavior remain. Missing league/unsupported rule version must fail before replacement; never persist partial results, fallback defaults or stale success. Context is local, so any later retry starts fresh even if the same service/connection object survives.

## Expected measured result

Freeze original November15 raw evidence. Update audit helper assertions explicitly to the new supplied-connection contract. Existing small fixture has N league/settings reads, or2N with fallback; target exactly1 per successful supplied call. Member-game and pair H2H counts, Week lock/delete/inserts are unchanged.

For N members and P=N(N−1)/2: untied target5+2N statements; H2H-decides addsP; unresolved/margin fallback addsP+N. At16members:52→37untied,172→157H2H-decides,204→173fallback. The120pair queries and fallback member-game rereads intentionally remain. These are independently checked synthetic statement counts, not promised production latency or full MOD021 completion.

## Verification for the implementation plan

- RED tests must prove actual supplied-connection member/fallback resolution occurs once, all consumers receive matching rules/conn, and no-context/no-conn helpers retain existing behavior. Missing members or invalid final period performs0rule reads.
- Freeze/reuse tests: caller settings mutation cannot mutate captured mapping; attempted context mutation rejected; a second week/league/call on the same service/connection reads fresh rules; mismatched context rejected before I/O; exception/retry discards it.
- Retain all weekly tie, week0, postseason, scoring service, atomic replacement, weekly completion/calendar maintenance and schedule-rule tests. Existing helper overrides/doubles need explicit migration only where supplied-connection contract applies.
- Native marked disposable PostgreSQL: five original scenarios at4/8/16members; exact returned and stored scores and current query formulas, including prior-score replacement/rollback. Extend with mixed tie groups, transferred historical ownership, dual ownership, tier/phase behavior, cross-league/cross-week isolation and final-period zero/split/future guards. A historical source/fixture reference or independent literal oracle must not reuse the new context code to compute its own expected scores.
- Controlled native interleaving changes rule source after context creation; current call uses captured rules, next call sees the new valid definition. Separately mutate tier/phase data and demonstrate unchanged live-read semantics with explicitly labelled scope; do not assert a coherent full snapshot. Preserve caller lock/connection/atomic rollback; do not add locks in fixture-only code and claim product locking.
- New unique RUNNING/PASS/FAILED evidence/source hashes, failure cleanup, exact owned resources removed; no configured database/provider/CLI/production role changes. Full guarded backend and relevant audit tests required. No frontend/browser/large index benchmark needed.

## Non-goals and release limits

No game/H2H batching, global cache, season-standing/bonus/finalization algorithm change, ownership/transaction reordering, full no-conn scorer refactor, status policy, SQL/index rollout or provider work. Whole-run consistency, production workloads/concurrent game corrections/tiers, and external consumers require separate acceptance. First batch can reduce redundant settings reads while leaving other known MOD021 costs unresolved.

Design status: approach selected by user; fresh builder check returned “nothing important left.” User approved the written design2026-11-16; implementation plan prepared separately. No product code changed.
