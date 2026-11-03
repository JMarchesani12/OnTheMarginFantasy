# MOD-038 Schedule Calendar Implementation Plan

> Use superpowers:executing-plans inline; test first and one fresh final review.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md). User approved schedule next; current checkout, leave sport/prior work intact and uncommitted.

**First bounded slice:** Extract league/settings/timezone/weekday/season-subdivision/week planning/insertion and season-phase lookup into ScheduleCalendarService with seven named repository queries. ScheduleModel inherits calendar behavior to preserve old methods, helper overrides, constructor and db-only instances. Canonical trusted entry points identify job/week-plan/timezone capabilities without constructing HTTP adapters or an ESPN client. Keep existing per-helper begin scopes (including separately committed Week0) and SQL byte-for-byte. Model retains other reads/ingestion/bootstrap for later slices. No new routes, actor policy, schemas/dependencies, startup/hosted/deploy changes. Disabled HTTP createWeeks remains410.

## Tasks

- [x] Guarded baseline524; RED real SQLite calendar/service tests covering DST/basketball/football, JSON timezone/weekday validation, subdivision selection and missing guards, existing-week reuse, bulk rollback/old Week0 partial commit and helper compatibility.
- [x] Extract13 methods and seven original queries, preserve remaining model AST and old constructor. Add explicit trusted entry points; no cross-domain caller migration until schedule composition is ready.
- [x] Native PostgreSQL dates/JSON/subdivision/phase joins/RETURNING, persisted boundaries, insert statement/deferred rollback and existing transaction behavior on marked owned loopback fixture. No worker/provider process startup.
- [x] Final full guarded suite, one fresh review, SQL/algorithm AST/import checks, current scoped evidence/docs/links/diff and owned-resource cleanup.

## Ledger

- Ruling: Calendar first supplies week/timezone/season capabilities consumed by both reads and ingestion; later slices will cover game/read projections, search and provider ingestion/bootstrap/composition. Do not label the whole schedule domain complete here.
- Ruling: Preserve helper dispatch through inheritance and lazily initialized stateless calendar repository; ScheduleModel constructor remains original, including espn_base_url normalization. Direct calendar service needs no provider URL/client.
- Ruling: Existing generation is not made atomic across Week0 and numbered-week helpers. Preserve committed Week0 if later bulk fails; global transaction/concurrency policy is separate correctness work.

- Baseline524/524 (including prior uncommitted sport). RED7 missing-service errors, GREEN7/7, full531/531. No existing tests modified.
- Extracted13 methods/seven queries. One-off AST check: migrated algorithms identical after query substitutions; all22 remaining methods including constructor unchanged; seven SQL ASTs exact. Root constants re-export canonical dictionaries. Canonical imports independent of provider/model/HTTP/configured engine.
- Native PASS7/7 queries: JSON/date/timestamptz/DST/RETURNING/subdivision/phase-final/postseason, existing rows, real statement/deferred-commit rollback and original football Week0 partial commit. No application bugfix or new atomicity/actor policy.
- Ruling: Calendar inheritance changes the ScheduleModel dependency hash captured by completed league evidence. Rerun existing full native league folders/lifecycle/callback verification against new source; PASS and report refreshed. Other completed-domain reports unchanged/current.
- Independent final review /root/schedule_calendar_review: no findings; fresh direct7/7; reviewed original/migrated AST/SQL/constructor/helper/transaction and native script. No implementation delegation.
- Final scoped evidence/docs/source hashes/links/diff checked; uniquely owned DBs removed by harnesses, named container stopped. Current checkout uncommitted; prior sport work preserved. Calendar foundations complete; schedule read projections/search, ingestion/bootstrap and final composition remain.
