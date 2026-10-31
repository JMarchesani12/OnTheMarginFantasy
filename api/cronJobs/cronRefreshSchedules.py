"""Run daily to refresh upcoming kickoff announcements and rescheduled games.

Unlike live score polling, this scans future sports days. The default three-week
window covers typical football TV announcements. Use --days 100 for a repair.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bootstrap import *
import argparse
import datetime as dt
import os
from zoneinfo import ZoneInfo
from sqlalchemy import text
from db import engine
from endpoints.schedule.scheduleModel import ScheduleModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--days', type=int, default=21)
    parser.add_argument('--sport-season-id', type=int)
    args = parser.parse_args()
    if args.days < 1:
        parser.error('--days must be positive')
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
    model = ScheduleModel(engine, os.getenv('ESPN_BASE_URL'))
    failures = []
    for season in seasons:
        start_day = max(today, season['seasonStart'].date() if isinstance(season['seasonStart'], dt.datetime) else season['seasonStart'])
        end_day = min(end, season['seasonEnd'].date() if isinstance(season['seasonEnd'], dt.datetime) else season['seasonEnd'])
        day = start_day
        while day <= end_day:
            try:
                print(model.ingest_scoreboard_for_date_for_sport_season(season['id'], day), flush=True)
            except Exception as exc:
                failures.append((season['id'], day.isoformat()))
                print(f'Refresh failed for season={season["id"]} date={day}: {exc}', flush=True)
            day += dt.timedelta(days=1)
    if failures:
        raise RuntimeError(f'Schedule refresh incomplete: {failures}')


if __name__ == '__main__':
    main()
