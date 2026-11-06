from zoneinfo import ZoneInfo
import datetime as dt
import os
from operations import job_gate, safe_event, run_id
from endpoints.schedule.ingestion_service import ScheduleIngestionService


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
            for day in dates:
                gate.check()
                leagues=service.active_leagues_for_job(day)
                for league in leagues:
                    gate.check()
                    try:
                        summary=service.ingest_league_for_job(league,day)
                        report['processed'].append({'leagueId':league,'date':day.isoformat()})
                        safe_event('ingest','unit_completed',identity,leagueId=league,date=day.isoformat(),count=summary.get('eventsSeen'))
                    except Exception as exc:
                        report['failures'].append({'leagueId':league,'date':day.isoformat()})
                        safe_event('ingest','failed',identity,leagueId=league,date=day.isoformat(),category=exc)
            gate.check()
    except Exception as exc:
        report['failures'].append({'leagueId':None})
        safe_event('ingest','failed',identity,category=exc)
    safe_event('ingest','failed' if report['failures'] else 'completed',identity,failures=len(report['failures']))
    return report


if __name__ == '__main__':
    if main()['failures']:raise SystemExit(1)
