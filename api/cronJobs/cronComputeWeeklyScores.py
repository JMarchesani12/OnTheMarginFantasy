import json
from operations import job_gate, safe_event, run_id

from endpoints.schedule.read_service import ScheduleReadService
from endpoints.scoring.service import ScoringService
from endpoints.scoring.weekly_service import WeeklyCompletionService
from endpoints.transaction.workflow_service import TransactionWorkflowService

def build_scoring(engine):
    schedule_model = ScheduleReadService(engine)
    scoring = ScoringService(engine, schedule_model)
    return scoring


def main(engine=None):
    identity = run_id()
    safe_event('weekly', 'started', identity)
    try:
        if engine is None:
            from runtime import configured_engine
            engine = configured_engine()
        with job_gate(engine, 'weekly') as gate:
            if not gate:
                safe_event('weekly', 'skipped', identity, category='already_running')
                report = dict({'applied': [], 'blocked': [], 'closed': [], 'failures': []}, outcome='already_running')
                print(json.dumps(report, sort_keys=True))
                return report
            gate.check()
            report = WeeklyCompletionService(engine, build_scoring(engine), TransactionWorkflowService(engine)).run()
            gate.check()
        safe_event('weekly', 'failed' if report['failures'] or report['blocked'] else 'completed', identity,
                   failures=len(report['failures']))
    except Exception as exc:
        safe_event('weekly', 'failed', identity, category=exc)
        report = {'applied': [], 'blocked': [], 'closed': [], 'failures': []}
        report['failures'].append({'leagueId': None, 'stage': 'job', 'category': type(exc).__name__})
    print(json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    outcome = main()
    if outcome['failures'] or outcome['blocked']:
        raise SystemExit(1)
