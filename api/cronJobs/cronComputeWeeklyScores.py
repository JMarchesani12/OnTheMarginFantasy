import json

from endpoints.schedule.read_service import ScheduleReadService
from endpoints.scoring.service import ScoringService
from endpoints.scoring.weekly_service import WeeklyCompletionService
from endpoints.transaction.workflow_service import TransactionWorkflowService

def build_scoring(engine):
    schedule_model = ScheduleReadService(engine)
    scoring = ScoringService(engine, schedule_model)
    return scoring


def main(engine=None):
    if engine is None:
        from runtime import configured_engine
        engine = configured_engine()
    service = WeeklyCompletionService(engine, build_scoring(engine), TransactionWorkflowService(engine))
    report = service.run()
    print(json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    outcome = main()
    if outcome['failures'] or outcome['blocked']:
        raise SystemExit(1)
