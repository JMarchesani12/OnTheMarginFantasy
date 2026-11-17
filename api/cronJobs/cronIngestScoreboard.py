from zoneinfo import ZoneInfo
import datetime as dt
import os
from operations import job_gate, safe_event, run_id
from endpoints.schedule.ingestion_service import ScheduleIngestionService
from endpoints.schedule.shared_ingestion_service import SharedScoreboardIngestionService


def get_active_leagues_for_date(engine, target_date: dt.date):
    return ScheduleIngestionService(engine, "").active_leagues_for_job(target_date)


def main(engine=None):
    identity=run_id();report={'processed':[], 'failures':[]}
    safe_event('ingest','started',identity)
    try:
        if engine is None:
            from runtime import configured_engine
            engine=configured_engine()
        with job_gate(engine,'ingest') as gate:
            if not gate:
                safe_event('ingest','skipped',identity,category='already_running')
                return dict(report,outcome='already_running')
            now=dt.datetime.now(ZoneInfo('America/Chicago'))
            dates=[now.date()]
            if now.hour<3:dates.append(now.date()-dt.timedelta(days=1))
            service=ScheduleIngestionService(engine,os.getenv('ESPN_BASE_URL',''))
            shared=SharedScoreboardIngestionService(service,gate.check)
            for day in dates:
                gate.check()
                leagues=service.active_leagues_for_job(day)
                for outcome in shared.iter_league_outcomes(leagues,day):
                    league=outcome['leagueId']
                    if outcome['error'] is None:
                        report['processed'].append({'leagueId':league,'date':day.isoformat()})
                        safe_event('ingest','unit_completed',identity,leagueId=league,date=day.isoformat(),count=outcome['summary'].get('eventsSeen'))
                    else:
                        report['failures'].append({'leagueId':league,'date':day.isoformat()})
                        safe_event('ingest','failed',identity,leagueId=league,date=day.isoformat(),category=outcome['error'])
            gate.check()
    except Exception as exc:
        report['failures'].append({'leagueId':None})
        safe_event('ingest','failed',identity,category=exc)
    safe_event('ingest','failed' if report['failures'] else 'completed',identity,failures=len(report['failures']))
    return report


if __name__ == '__main__':
    if main()['failures']:raise SystemExit(1)
