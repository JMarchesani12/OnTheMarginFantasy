# Schedule extraction boundaries

Calendar and week foundations are implemented in `calendar_service.py` / `calendar_repository.py`: league/settings/timezone/weekday, sport-season/subdivision selection, week lookup/creation/planning and season-phase lookup. Named repository methods use supplied connections; the service preserves original per-helper transactions and policy.

Trusted capabilities are `ensure_weeks_for_job`, `boundaries_for_job` and `timezone_for_job`. A calendar service needs only the database, with no provider URL/client or HTTP adapter. These are internal capabilities; HTTP week generation remains disabled (410).

`ScheduleModel` inherits calendar methods to preserve legacy helper overrides, db-only instances and existing constructor semantics. Weekday constants are re-exported as shared objects at the old module path. Other schedule read, ingestion/bootstrap and caller composition work remains in the model for subsequent slices; the entire schedule model is not yet SQL-free. Existing cross-domain callbacks continue through this compatibility API until their composition slice.

Preserve existing partial-commit behavior: football Week0 uses a separate transaction and survives a later numbered-week batch failure. This extraction does not change replay/concurrency/global atomicity, calendar policies or application/job/provider startup.

[Native calendar evidence](../../../docs/modernization/evidence/mod-038-schedule-calendar-postgres-2026-10-30.json), [plan/ledger](../../../docs/superpowers/plans/2026-10-30-mod-038-schedule-calendar-implementation.md).
