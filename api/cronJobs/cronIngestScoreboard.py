from zoneinfo import ZoneInfo
from bootstrap import *
import datetime as dt
from sqlalchemy import text
import os
from dotenv import load_dotenv
from db import engine

from endpoints.schedule.scheduleModel import ScheduleModel

def get_active_leagues_for_date(engine, target_date: dt.date):
    """
    Returns league ids that:
      - have a SportSeason row
      - and where target_date is between regularSeasonStart and playoffEnd
      - and league.status is not 'Completed'
    """
    sql = text("""
        SELECT l.id
        FROM "League" l
        JOIN "SportSeason" ss
          ON ss."sportId" = l."sport"
         AND ss."seasonYear" = l."seasonYear"
        WHERE
          ss."regularSeasonStart"::date <= :d
          AND ss."playoffEnd"::date >= :d
          AND l.status <> 'Completed'
    """)

    with engine.begin() as conn:
        rows = conn.execute(sql, {"d": target_date}).fetchall()

    return [int(r[0]) for r in rows]


def main():
    central = ZoneInfo("America/Chicago")

    sports_day = dt.datetime.now(central).date()   # date for DB

    load_dotenv()

    schedule_model = ScheduleModel(engine, os.getenv("ESPN_BASE_URL"))

    league_ids = get_active_leagues_for_date(engine, sports_day)
    print(f"[cron] {sports_day} - Found {len(league_ids)} active leagues")

    for league_id in league_ids:
        try:
            summary = schedule_model.ingest_scoreboard_for_date_for_league(league_id, sports_day)
            print(f"[cron] League {league_id}: eventsSeen={summary['eventsSeen']}")
        except Exception as e:
            print(f"[cron] ERROR ingesting for league {league_id}: {e}")



if __name__ == "__main__":
    main()
