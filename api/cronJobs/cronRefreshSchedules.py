"""Run daily to refresh upcoming kickoff announcements and rescheduled games.

Unlike live score polling, this scans future sports days. The default three-week
window covers typical football TV announcements. Use --days 100 for a repair.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse
import datetime as dt
import os
from zoneinfo import ZoneInfo
from sqlalchemy import text
from operations import job_gate, safe_event, run_id
from endpoints.schedule.ingestion_service import ScheduleIngestionService


def main(argv=None, engine=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=21)
    parser.add_argument('--sport-season-id', type=int)
    args = parser.parse_args(argv)
    if args.days < 1:
        parser.error('--days must be positive')
    identity=run_id()
    safe_event('refresh','started',identity)
    try:
        return _run(args, engine, identity)
    except Exception as exc:
        safe_event('refresh','failed',identity,category=exc)
        raise RuntimeError('Schedule refresh incomplete') from None


def _run(args, engine, identity):
    if engine is None:
        from runtime import configured_engine
        engine = configured_engine()
    with job_gate(engine,'refresh') as gate:
        if not gate:
            safe_event('refresh','skipped',identity,category='already_running')
            return {'outcome':'already_running'}
        gate.check()
        today = dt.datetime.now(ZoneInfo('America/Chicago')).date()
        end = today + dt.timedelta(days=args.days - 1)
        with engine.connect() as conn:
            seasons = conn.execute(text('''
                SELECT DISTINCT ss.id, ss."seasonStart", ss."seasonEnd"
                FROM "SportSeason" ss
                JOIN "League" l ON l.sport = ss."sportId"
                    AND l."seasonYear" = ss."seasonYear"
                WHERE l.status <> 'Completed'
                  AND ss."seasonEnd"::date >= :today
                  AND ss."seasonStart"::date <= :end
                  AND (:id IS NULL OR ss.id = :id)
            '''), {'today': today, 'end': end, 'id': args.sport_season_id}).mappings().all()
        model = ScheduleIngestionService(engine, os.getenv('ESPN_BASE_URL', ''))
        failures = []
        for season in seasons:
            start_day = max(today, season['seasonStart'].date() if isinstance(season['seasonStart'], dt.datetime) else season['seasonStart'])
            end_day = min(end, season['seasonEnd'].date() if isinstance(season['seasonEnd'], dt.datetime) else season['seasonEnd'])
            day = start_day
            while day <= end_day:
                gate.check()
                try:
                    model.ingest_season_for_job(season['id'], day)
                    safe_event('refresh','unit_completed',identity,sportSeasonId=season['id'],date=day.isoformat())
                except Exception as exc:
                    failures.append((season['id'], day.isoformat()))
                    safe_event('refresh','failed',identity,sportSeasonId=season['id'],date=day.isoformat(),category=exc)
                day += dt.timedelta(days=1)
        if failures:
            raise RuntimeError('Schedule refresh incomplete')
        gate.check()
    safe_event('refresh','completed',identity)
    return {'outcome':'completed'}


if __name__ == '__main__':
    try:main()
    except Exception:
        raise SystemExit(1) from None
