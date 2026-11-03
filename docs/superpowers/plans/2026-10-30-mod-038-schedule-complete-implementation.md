# MOD-038 Schedule Completion Implementation Plan

> Execute inline with superpowers:executing-plans, test first and one final fresh review.

**Spec:** [Approved hybrid](../specs/2026-10-29-mod-038-layering-design.md); user explicitly requests finishing remaining schedule/domain work. Current checkout, preserve existing work, leave uncommitted.

## Task 1: Remaining ingestion/bootstrap

- [x] Baseline545; RED direct canonical ingestion/HTTP composition tests before implementation.
- [x] Move10 ingestion/bootstrap methods and12 exact persistence queries into ingestion_service.py/ingestion_repository.py; injected provider factory with unchanged default ESPNClient/timeout behavior. Move pure tier compatibility helper into read service, retain exact root constructor and inherited overrides/db-only behavior in SQL-free facade.
- [x] Preserve team/date fetch/error/count/dedupe distinctions, helper transaction scopes, per-game commits, caller-connection season upsert, phase selection and all checkpoint fingerprint/save/resume/force/completion ordering.

## Task 2: Concrete caller composition

- [x] HTTP read service aggregate keeps original scopes, rules/envelopes/parsing/errors/auth; manual week generation stays410. League callbacks/read/scoring constructors use canonical services, legacy injected scheduleModel facade attribute remains supported.
- [x] Scoring builders/routes use read service without ESPN URL; ingest cron/start-season use explicit trusted ingestion methods; active-league SQL becomes13th ingestion repository query. Rebuild uses exposed calendar season/boundary capabilities. No actual jobs/provider/network/app startup.
- [x] Update only moved test seams; verify real HTTP/compiled job builders without configured imports.

## Task 3: Complete verification and records

- [x] Native all13 ingestion queries, upsert conflict/phase/JSON/groups/limit filters, caller/statement/deferred rollback, fake-provider actual parsing/per-game partial commits and temp checkpoint resume/force/failure; rerun all read/calendar/league and affected scoring native suites.
- [x] All guarded tests, one fresh review, original algorithm/SQL AST comparison and current scoped source hashes/docs/links/diff. Remove only owned DB/container.

## Constraints / ledger

- No schema/dependency/hosted/deploy/startup/retry/timeout/rate-limit policy changes. Native owned fixture only; provider traffic is synthetic/injected. No frontend work or new authorization/profile/visibility policy.
- Ruling: Existing team bootstrap marks complete despite individual fetch failures; league ingestion counts parsed/skipped events differently and does not dedupe like sport-season ingestion. Preserve these behaviors rather than merging algorithms.
- Ruling: Keep legacy ScheduleModel constructor/body and method dispatch; canonical ingestion constructor initializes stateless repositories and optional client factory. Canonical read callers no longer require provider configuration; existing dotenv/startup calls otherwise remain.
- Ruling: Keep compatibility-shaped public read methods for scoring consumers; constructors now receive actual read service. Expose season_for_job for rebuild rather than crossing private model helpers. Legacy LeagueModel injected scheduleModel callbacks retain their old method protocol.

- Baseline545/545. New ingestion7 and composition5 cases RED before implementation, then GREEN12/12; full557/557. Existing composition tests changed only moved seams.
- Extraction proof: all35 original method algorithms and29 model+1cron SQL ASTs exact after named-query/client substitutions; exact root constructor retained. Dynamic optional team LIMIT moves to repository keyed by existing maxTeams parameter, covering None/0/1. No policy change.
- Native complete PASS all30 queries (7/10/13), real parser with fake fetches, ON CONFLICT/rich+fallback phase/JSON/null/LIMIT/rollback/current connection, per-game partial commits, temporary checkpoint partial/resume/force/retry/skip and final metadata commit failure convergence. Full native league and scoring suites PASS; affected source reports refreshed.
- Independent fresh review /root/schedule_complete_final_review: no Critical/Important/Minor findings, fresh557/557 and source AST proof. Final harness additionally asserts read query coverage union; no application edits after review.
- Ruling/correction: Final eight-model audit disproved the earlier “only sport/schedule left” count. Transaction pilot still has22 SQL-bearing trade/free-agency/dispatch/read methods. Correct user/docs immediately; schedule completion does not complete overall backend rollout. Do not silently expand this finished schedule task into a large transaction rewrite. Audit source hashes/method inventory recorded for next work.
- Final records: current scoped source hashes/links/diff checked; legacy facades kept, owned databases/container/checkpoint directories removed. No commit/push/merge/deploy/schema/dependency/hosted/provider/job startup. Schedule domain complete; remaining transaction rollout and broader modernization clearly open.
