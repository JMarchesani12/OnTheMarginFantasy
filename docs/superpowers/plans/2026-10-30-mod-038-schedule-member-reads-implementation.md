# MOD-038 Schedule Member Reads Implementation Plan

> Execute inline with superpowers:executing-plans, test first and one fresh review.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md); user requested next bounded slice. Current checkout; retain sport/calendar work; uncommitted/no deploy.

**Scope:** Four related methods: member-week games with tier/tournament calculation, head-to-head games, league week record and owned-team projection. Add read_service.py/read_repository.py. ScheduleReadService inherits calendar capabilities; ScheduleModel inherits read service, retaining constructor and helper overrides/db-only compatibility. Preserve original SQL/result accessors/per-helper begin scopes and scoring functions. Named trusted entry points for scoring/composition, with remaining HTTP and job adapter wiring deferred until schedule capabilities are ready. No new actor/profile/visibility policy or HTTP contract changes; disabled week generation stays410.

## Tasks

- [x] Baseline531 and direct service RED→GREEN: ownership perspectives/double-owned, phase scoring, supplied/default/invalid rules, plain projections/missing rows, failure unwind and legacy helper override.
- [x] Extract four algorithms/four exact SQL queries, preserve18 remaining model methods and calendar inheritance. No provider/configured-engine/HTTP imports in canonical layers.
- [x] Native PostgreSQL actual ownership/date/season/league/tier/phase/fallback joins and projection/error/no-write behavior; rerun calendar and existing league callbacks on current source.
- [x] Full guarded suite, independent review, algorithm/query AST checks, scoped source evidence/docs/diff/links and owned-resource cleanup.

## Ledger

- Ruling: Inheritance retains self._get_league dispatch and constructor/db-only compatibility for scoring/league consumers. Calendar stays the shared internal capability; read repository is stateless and initialized lazily for legacy construction.
- Ruling: Preserve head-to-head's original NULL-start behavior and owned-team conference membership joins (including no season restriction there); do not silently unify them with other reads. Broader authorization/atomic snapshot/correctness work remains separate.
- Ruling: This slice supplies read capabilities through the compatibility facade; final transport/job composition stays a separate schedule slice rather than changing auth/profile-resolution policy incidentally.

- Baseline531/531; RED7 missing service; GREEN7/7; full538/538. Existing tests unchanged.
- Four algorithms and SQL ASTs identical after named-query substitution;18 remaining model methods including constructor unchanged. Canonical imports independent of model/HTTP/configured engine/provider; lazy repository supports legacy .db.
- Native PASS4/4 plus all7 calendar cases, actual filtering/joins/scoring/projections/no-write/errors/legacy. Original NULL scores trigger TypeError; preserve this observed behavior rather than silently changing scoring policy. H2H NULL-start and unfiltered owned memberships also preserved.
- Ruling: New combined read+calendar report supersedes earlier calendar model hash; prior report historical. Rerun full native league callback suites and refresh changed dependency capture; PASS. Other completed-domain source reports remain current.
- Independent final review /root/schedule_member_reads_review: no findings, fresh direct7/7, exact SQL and untouched method comparison; no implementation delegation.
- Final: current scoped source hashes/internal links/diff verified, owned temporary DBs removed and named container stopped. No commit/merge/push/deploy/schema/dependency/hosted/startup work. Existing uncommitted work preserved. Next: other views/search, then ingestion/bootstrap and final composition.
