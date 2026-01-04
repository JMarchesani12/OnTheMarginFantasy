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
    now = dt.datetime.now(central)

    # Always ingest "today" in Central
    dates_to_ingest = [now.date()]

    # If it's shortly after midnight, also ingest "yesterday" to catch late OT / late finals
    LATE_WINDOW_HOUR = 3
    if now.hour < LATE_WINDOW_HOUR:
        dates_to_ingest.append(now.date() - dt.timedelta(days=1))

    load_dotenv()

    schedule_model = ScheduleModel(engine, os.getenv("ESPN_BASE_URL"))

    for sports_day in dates_to_ingest:
        # date string for logging clarity (and for ESPN if you ever need it)
        sports_day_str = sports_day.strftime("%Y%m%d")

        league_ids = get_active_leagues_for_date(engine, sports_day)
        print(f"[cron] ingestDate={sports_day_str} ({sports_day}) - Found {len(league_ids)} active leagues")

        for league_id in league_ids:
            try:
                summary = schedule_model.ingest_scoreboard_for_date_for_league(league_id, sports_day)
                print(f"[cron] League {league_id} ingestDate={sports_day_str}: eventsSeen={summary['eventsSeen']}")
            except Exception as e:
                print(f"[cron] ERROR ingesting league {league_id} ingestDate={sports_day_str}: {e}")



if __name__ == "__main__":
    main()
