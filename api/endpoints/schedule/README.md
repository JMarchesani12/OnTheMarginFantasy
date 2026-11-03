# Schedule domain boundaries

| Responsibility | Canonical service | SQL owner |
| --- | --- | --- |
| League/settings/timezone/weekdays/season-subdivisions, week planning/creation, phase lookup | calendar_service.py | calendar_repository.py |
| Member/H2H/week/owned-team, conference/team-season views, normalization/ranking/search, member response composition | read_service.py | read_repository.py |
| Provider config/team lookup, game/season upsert, phase selection, ingestion/bootstrap/checkpoint and active-league facts | ingestion_service.py | ingestion_repository.py |

Services own the original helper transaction scopes. Repositories use supplied connections, including caller-owned season metadata transactions. Read service inherits calendar; ingestion service inherits reads for legacy shared helper dispatch. Canonical layers import no compatibility model, Flask handler or configured engine. Ingestion accepts an optional client factory; default ESPN client/parser/timeout behavior is unchanged.

The former ScheduleModel facade is retired. Read/calendar consumers use their canonical services; ingestion/bootstrap consumers use ScheduleIngestionService. Existing helper overrides remain on these services. No planned schedule content/wiring slice remains.

Schedule HTTP uses read service, retaining input/envelopes/errors and authentication; week generation stays410. League callbacks and scoring constructors receive read service without provider URL/client construction. Ingest cron and season setup use named trusted ingestion operations; metadata upsert receives the existing caller connection. Rebuild uses public calendar season/boundary capabilities. League HTTP composition injects schedule and lifecycle callbacks directly. Existing public read method shapes remain available to scoring services.

Preserve original behavior: football Week0 commits separately; each game upsert commits separately; sport-season ingestion dedupes groups while league ingestion counts differently; team bootstrap marks complete even after per-team fetch failures; checkpoint fingerprint/save/resume/force and file-before-final-metadata ordering remain. No new cross-resource atomicity, replay, publication, score, actor/visibility, retry/timeout or startup policy is implied.

[Current complete schedule evidence](../../../docs/modernization/evidence/mod-038-schedule-complete-postgres-2026-11-02.json) covers all30 queries (7 calendar/10 read/13 ingestion), actual parser with synthetic fetches and owned temporary checkpoints. Earlier slice reports are historical. [Completion ledger](../../../docs/superpowers/plans/2026-10-30-mod-038-schedule-complete-implementation.md).
