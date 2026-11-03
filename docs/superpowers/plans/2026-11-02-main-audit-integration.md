# Main into audit integration

User authorized resolving the existing merge, preserving main fixes and equal current schema, with MOD-025 deferred. Updating main triggers production; no push or main update is authorized by this resolution task.

## Work
- [x] Adapt main's timezone tests to canonical LeagueLifecycleService and reproduce missing fixes.
- [x] Add persistence/projection checks for timeTBD and reproduce missing coverage.
- [x] Port main's lifecycle and schedule changes into canonical repositories/services; retain retired Model deletions.
- [x] Migrate new refresh job to explicit engine injection/canonical service; test startup and arguments with fakes.
- [x] Combine README instructions; preserve main's current db/tables.sql and migration byte-for-byte; document frozen baseline upgrade sequence.
- [x] Verify full backend/frontend/build, migration behavior on disposable local DB if available, and current schema/migration parity with main.
- [x] Resolve/stage conflicted files and get fresh whole-change review. Leave merge uncommitted and do not deploy.

## Evidence and rulings
- Merge parent: ae8a103c7c35ec7ecfa4e6dcf4f5735002c146a8 (main), audit HEAD includes MOD-034.
- Conflicts initially: api/README.md; retired leagueModel.py and scheduleModel.py.
- Preserve frozen baseline/checksums; never rewrite historical schema evidence to pretend it includes timeTBD.

- RED: adapted main timezone4/4 failed on audit's old lifecycle; kickoff persistence3/3 failed on absent service binding/SQL/projections; refresh3/3 failed on retired db engine import.
- GREEN: canonical lifecycle SQL normalized against main's original function matches all five statements exactly. Current schema and migration byte-identical to main; frozen baseline package unchanged.
- Existing SQLite lifecycle fixture adapts only PostgreSQL local-date syntax to its fixed UTC clock; expected undrafted statuses now reflect main's intentional change. Boundary cases retain completed-draft fixtures. Real timezone paths separately run on PostgreSQL.
- Verification: backend593/593, frontend64/64, frontend build, native PostgreSQL migration/schedule/lifecycle/timezone checks pass. Native report stored separately; historical evidence retained.
- Configured database read-only column metadata: timeTBD boolean, NOT NULL, default false. No hosted DDL or application rows read/exported. This is a bounded column check, not a fresh full-schema comparison.
- Final self-review found an unintended extra timeTBD sort key introduced during porting. Equal-date/mixed-flag native regression reproduced it; removed the extra key so main's date/externalGameId ordering is preserved. Rerun native checks pass.
- Fresh reviewer found no remaining material integration issues on final re-review, including ordering correction. Owned disposable container/volumes removed; generated test databases were dropped by the harness.
- Merge conflicts resolved in index; leave merge uncommitted. No update to main, push, deployment, real cron/provider call or MOD-025 work.
