"""Configured CLI adapter; season validation/completion lives outside HTTP."""
import json
from operations import job_gate, safe_event, run_id
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.scoring.service import ScoringService
from endpoints.scoring.finalization_service import SeasonFinalizationService


def build_scoring(engine):
    schedule_model = ScheduleReadService(engine)
    return ScoringService(engine, schedule_model)


def main(engine=None):
    identity = run_id()
    safe_event('finalization', 'started', identity)
    try:
        if engine is None:
            from runtime import configured_engine
            engine = configured_engine()
        with job_gate(engine, 'finalization') as gate:
            if not gate:
                safe_event('finalization', 'skipped', identity, category='already_running')
                report = dict({'finalized': [], 'skipped': [], 'blocked': [], 'failures': []}, outcome='already_running')
                print(json.dumps(report, sort_keys=True))
                return report
            gate.check()
            report = SeasonFinalizationService(engine, build_scoring(engine)).run()
            gate.check()
        safe_event('finalization', 'failed' if report['failures'] or report['blocked'] else 'completed', identity,
                   failures=len(report['failures']))
    except Exception as exc:
        safe_event('finalization', 'failed', identity, category=exc)
        report = {'finalized': [], 'skipped': [], 'blocked': [], 'failures': []}
        report['failures'].append({'sportSeasonId': None, 'stage': 'job', 'category': type(exc).__name__})
    print(json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    outcome = main()
    if outcome['failures'] or outcome['blocked']:
        raise SystemExit(1)
