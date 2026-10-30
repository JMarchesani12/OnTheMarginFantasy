# MOD-038 Schedule Views and Search Implementation Plan

> Execute inline with superpowers:executing-plans; test first, one fresh final review.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md); user requested next slice. Current checkout, preserve prior work/uncommitted, no deployment.

**Scope:** Move6 methods (week-window helper, conference games, team-season games, search normalization/ranking/query) and6 exact SQL queries into existing ScheduleReadService/Repository. Root model inherits them, preserving constructor and remaining12 methods. Add explicit internal conference/team/search capabilities for later composition. Keep current ranking/clamping, missing/null behavior, owner projection and all transaction/query scopes. No actor/visibility/profile policy, HTTP parsing/error/envelope or provider/job startup changes. HTTP/cross-domain/job wiring is still deferred until final schedule composition.

## Tasks

- [x] Baseline538; RED→GREEN tests ranking/normalization/clamp/short-query no-I/O, missing league/window, optional owner context/fallback, projection/transaction/error/legacy overrides.
- [x] Move6 algorithms/6 queries unchanged; preserve existing4 read algorithms/queries and12 remaining model methods. Pure decorators and helper dispatch retained.
- [x] Native PostgreSQL LATERAL current/latest/999 context, optional league NULL binds, season/conference/date/ownership filtering and exact projection/search ranking. Rerun member/calendar/league callbacks; combined read query coverage10/10.
- [x] Full guarded suite, one fresh review, AST/source hashes/docs/links/diff, owned resource cleanup.

## Ledger

- Ruling: Extend existing read service/repository instead of adding another inheritance layer; these are read projections and search, not provider ingestion.
- Ruling: Preserve conference window's separate transaction and team-season/search context+rows in one transaction. Owner context is current/latest/999 for the whole season view, not historical ownership at each game's date.
- Ruling: Preserve OR/null season membership behavior and potential duplicate search rows, existing missing-league distinctions (search raises, optional team context falls back), limit coercion before short-query guard, and unguaranteed tie ordering among identical rows.

- Baseline538/538. RED8 expected missing-method errors across7 tests/subtests with old legacy case passing; GREEN7/7. Full545/545. Existing backend tests unchanged.
- Source-preserving extraction:6 moved algorithms/SQL ASTs exact, all pre-existing read service/repository methods unchanged, remaining12 model methods incl constructor exact. Decorators and self/cls helper dispatch preserved; canonical import boundaries checked.
- Native PASS6 new queries plus4 member/all7 calendar queries: LATERAL current/latest/999, optional NULL league context, conference/season/date/ownership/opponent/projection/rank/limit/duplicate/missing/read failures/no-writes/legacy. No production bugfix or SQL changes.
- Ruling: Prior native member harness dynamically expected every read repository method. Scope that harness to its original4; new combined harness asserts the union of4+6 equals all10 repository methods. Existing member checks unchanged, full prior cases rerun.
- Full native league/lifecycle/callback rerun PASS; dependency hash refreshed. New combined report supersedes earlier member/calendar source captures; prior reports historical. Other completed-domain source captures remain current.
- Fresh review /root/schedule_views_search_review: no findings, independently7/7 and AST/source comparison; no implementation delegation.
- Final source hashes/docs/internal links/diff checked, owned DBs removed and named container stopped. Prior work preserved; checkout uncommitted; no schema/dependencies/hosted/deploy/startup work. Remaining: ingestion/bootstrap and final caller composition.
