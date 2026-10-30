from zoneinfo import ZoneInfo
from bootstrap import *
import datetime as dt
import os
from dotenv import load_dotenv
from db import engine

from endpoints.schedule.ingestion_service import ScheduleIngestionService

def get_active_leagues_for_date(engine, target_date: dt.date):
    return ScheduleIngestionService(engine, "").active_leagues_for_job(target_date)


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

    schedule_model = ScheduleIngestionService(engine, os.getenv("ESPN_BASE_URL"))

    for sports_day in dates_to_ingest:
        # date string for logging clarity (and for ESPN if you ever need it)
        sports_day_str = sports_day.strftime("%Y%m%d")

        league_ids = schedule_model.active_leagues_for_job(sports_day)
        print(f"[cron] ingestDate={sports_day_str} ({sports_day}) - Found {len(league_ids)} active leagues")

        for league_id in league_ids:
            try:
                summary = schedule_model.ingest_league_for_job(league_id, sports_day)
                print(f"[cron] League {league_id} ingestDate={sports_day_str}: eventsSeen={summary['eventsSeen']}")
            except Exception as e:
                print(f"[cron] ERROR ingesting league {league_id} ingestDate={sports_day_str}: {e}")



if __name__ == "__main__":
    main()
