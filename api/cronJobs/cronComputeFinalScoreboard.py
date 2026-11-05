"""Configured CLI adapter; season validation/completion lives outside HTTP."""
import json
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.scoring.service import ScoringService
from endpoints.scoring.finalization_service import SeasonFinalizationService


def build_scoring(engine):
    schedule_model = ScheduleReadService(engine)
    return ScoringService(engine, schedule_model)


def main(engine=None):
    try:
        if engine is None:
            from runtime import configured_engine
            engine = configured_engine()
        report = SeasonFinalizationService(engine, build_scoring(engine)).run()
    except Exception as exc:
        report = {'finalized': [], 'skipped': [], 'blocked': [], 'failures': [
            {'sportSeasonId': None, 'stage': 'job', 'category': type(exc).__name__},
        ]}
    print(json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    outcome = main()
    if outcome['failures'] or outcome['blocked']:
        raise SystemExit(1)
