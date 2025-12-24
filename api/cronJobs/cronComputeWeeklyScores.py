from bootstrap import *
import os
from db import engine
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import text

from endpoints.schedule.scheduleModel import ScheduleModel
from endpoints.scoring.scoringEndpoints import ScoringEndpoints
from endpoints.transaction.transactionModel import TransactionModel

def build_scoring(engine):
    load_dotenv()
    espn_base_url = os.getenv("ESPN_BASE_URL")
    schedule_model = ScheduleModel(engine, espn_base_url)
    scoring = ScoringEndpoints(engine, schedule_model)
    return scoring


GET_WEEKS_JUST_ENDED = text("""
    -- Pick ONLY the most-recent ended, unscored week per league
    SELECT DISTINCT ON (w."leagueId")
        w.id,
        w."leagueId"   AS "leagueId",
        w."weekNumber" AS "weekNumber",
        w."endDate"    AS "endDate"
    FROM "Week" w
    WHERE w."endDate" < :now
      AND w."scoringComplete" = FALSE
    ORDER BY w."leagueId", w."endDate" DESC
""")

MARK_WEEK_SCORED = text("""
    UPDATE "Week"
       SET "scoringComplete" = TRUE
     WHERE id = :week_id
""")

LOCK_NEXT_WEEK = text("""
    UPDATE "Week"
       SET "isLocked" = TRUE
     WHERE "leagueId" = :league_id
       AND "weekNumber" = :next_week_number
""")

GET_PENDING_TRADES = text("""
    SELECT id
    FROM "Transaction"
    WHERE status = 'PENDING_APPLY'
""")


def main():
    scoring = build_scoring(engine)
    transaction_model = TransactionModel(engine)

    now = datetime.now(timezone.utc)

    # 1) Find "just ended" weeks (1 per league)
    with engine.begin() as conn:
        weeks_to_score = conn.execute(GET_WEEKS_JUST_ENDED, {"now": now}).fetchall()

    if not weeks_to_score:
        print("No weeks to score.")
        return

    # 2) Score each (league, week), mark complete, lock next week
    for row in weeks_to_score:
        league_id = int(row._mapping["leagueId"])
        week_number = int(row._mapping["weekNumber"])
        week_id = int(row._mapping["id"])

        print(f"Scoring league {league_id}, week {week_number} (Week.id={week_id})")

        # If scoring throws, we do NOT want to mark complete or lock next week.
        try:
            scoring.score_week(league_id, week_number)
        except Exception as e:
            print(f"ERROR scoring league {league_id} week {week_number}: {e}")
            continue

        next_week_number = week_number + 1

        with engine.begin() as conn:
            conn.execute(MARK_WEEK_SCORED, {"week_id": week_id})
            conn.execute(
                LOCK_NEXT_WEEK,
                {"league_id": league_id, "next_week_number": next_week_number},
            )

    # 3) Apply trades after scoring
    with engine.begin() as conn:
        trade_rows = conn.execute(GET_PENDING_TRADES).fetchall()

    for tr in trade_rows:
        transaction_model.apply_trade(int(tr._mapping["id"]))

    print("Weekly scoring, next-week locking, and trades complete.")


if __name__ == "__main__":
    main()
