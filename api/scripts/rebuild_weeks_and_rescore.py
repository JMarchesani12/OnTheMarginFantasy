import os
import argparse
import datetime as dt

from sqlalchemy import text

from endpoints.schedule.scheduleModel import ScheduleModel
from endpoints.scoring.scoringModel import ScoringModel


GET_ALL_LEAGUES = text("""
    SELECT id
    FROM "League"
    ORDER BY id
""")

GET_LEAGUES_WITHOUT_SPORTSEASON = text("""
    SELECT l.id, l."sport", l."seasonYear"
    FROM "League" l
    LEFT JOIN "SportSeason" ss
      ON ss."sportId" = l."sport"
     AND ss."seasonYear" = :seasonYear
    WHERE ss.id IS NULL
    ORDER BY l.id
""")

GET_EXISTING_WEEKS = text("""
    SELECT id, "weekNumber"
    FROM "Week"
    WHERE "leagueId" = :leagueId
    ORDER BY "weekNumber" ASC
""")

UPDATE_WEEK = text("""
    UPDATE "Week"
    SET "startDate" = :startDate,
        "endDate" = :endDate
    WHERE "leagueId" = :leagueId
      AND "weekNumber" = :weekNumber
    RETURNING id
""")

INSERT_WEEK = text("""
    INSERT INTO "Week"
        ("leagueId", "weekNumber", "startDate", "endDate", "isLocked", "scoringComplete")
    VALUES
        (:leagueId, :weekNumber, :startDate, :endDate, false, false)
    RETURNING id
""")

DELETE_WEEKLY_SCORES = text("""
    DELETE FROM "WeeklyTeamScore"
    WHERE "leagueId" = :leagueId
""")

DELETE_EXTRA_WEEKLY_SCORES = text("""
    DELETE FROM "WeeklyTeamScore"
    WHERE "leagueId" = :leagueId
      AND "weekId" IN (
          SELECT id
          FROM "Week"
          WHERE "leagueId" = :leagueId
            AND "weekNumber" = ANY(:weekNumbers)
      )
""")

DELETE_EXTRA_WEEKS = text("""
    DELETE FROM "Week"
    WHERE "leagueId" = :leagueId
      AND "weekNumber" = ANY(:weekNumbers)
""")

RESET_SCORING_COMPLETE = text("""
    UPDATE "Week"
    SET "scoringComplete" = FALSE
    WHERE "leagueId" = :leagueId
""")

GET_ENDED_WEEKS = text("""
    SELECT id, "weekNumber"
    FROM "Week"
    WHERE "leagueId" = :leagueId
      AND "weekNumber" >= 0
      AND "endDate" IS NOT NULL
      AND "endDate" < :now
    ORDER BY "weekNumber" ASC
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


def _compute_week_boundaries(
    schedule_model: ScheduleModel,
    league_id: int,
    season_year: int,
):
    season = schedule_model._get_sport_season_for_league(league_id)
    if int(season["seasonYear"]) != season_year:
        raise ValueError(
            f"League {league_id} belongs to seasonYear={season['seasonYear']}, "
            f"not requested seasonYear={season_year}"
        )
    return schedule_model.get_week_boundaries(league_id)


def main():
    parser = argparse.ArgumentParser(description="Deliberately rebuild league weeks and rescore ended periods.")
    parser.add_argument("--season-year", type=int, required=True)
    parser.add_argument("--league-id", type=int, action="append", help="Limit to specific league IDs")
    args = parser.parse_args()
    from db import engine
    season_year = args.season_year
    schedule_model = ScheduleModel(engine, os.getenv("ESPN_BASE_URL", ""))
    scoring_model = ScoringModel(engine, schedule_model)

    with engine.begin() as conn:
        league_rows = conn.execute(GET_ALL_LEAGUES).fetchall()
        missing_rows = conn.execute(
            GET_LEAGUES_WITHOUT_SPORTSEASON,
            {"seasonYear": season_year},
        ).fetchall()

    league_ids = [int(r[0]) for r in league_rows if not args.league_id or int(r[0]) in args.league_id]
    if not league_ids:
        print("No leagues found.")
        return
    if missing_rows:
        missing = [dict(r._mapping) for r in missing_rows]
        print(f"Leagues missing SportSeason {season_year} match (will skip): {missing}")

    now = dt.datetime.now(dt.timezone.utc)

    for league_id in league_ids:
        print(f"Rebuilding weeks and rescoring league {league_id}")

        try:
            week_boundaries = _compute_week_boundaries(
                schedule_model,
                league_id,
                season_year=season_year,
            )
        except ValueError as exc:
            print(f"  Skipping league {league_id}: {exc}")
            continue

        with engine.begin() as conn:
            existing = conn.execute(GET_EXISTING_WEEKS, {"leagueId": league_id}).fetchall()
            existing_numbers = {int(r._mapping["weekNumber"]) for r in existing}

            for week_number, start_dt, end_dt in week_boundaries:
                updated = conn.execute(
                    UPDATE_WEEK,
                    {
                        "leagueId": league_id,
                        "weekNumber": week_number,
                        "startDate": start_dt,
                        "endDate": end_dt,
                    },
                ).fetchone()

                if not updated:
                    conn.execute(
                        INSERT_WEEK,
                        {
                            "leagueId": league_id,
                            "weekNumber": week_number,
                            "startDate": start_dt,
                            "endDate": end_dt,
                        },
                    )

            computed_numbers = {wn for wn, _, _ in week_boundaries}
            extra_numbers = sorted(existing_numbers - computed_numbers)
            if extra_numbers:
                print(f"  Removing extra weeks for league {league_id}: {extra_numbers}")
                conn.execute(
                    DELETE_EXTRA_WEEKLY_SCORES,
                    {"leagueId": league_id, "weekNumbers": extra_numbers},
                )
                conn.execute(
                    DELETE_EXTRA_WEEKS,
                    {"leagueId": league_id, "weekNumbers": extra_numbers},
                )

        with engine.begin() as conn:
            conn.execute(DELETE_WEEKLY_SCORES, {"leagueId": league_id})
            conn.execute(RESET_SCORING_COMPLETE, {"leagueId": league_id})

        with engine.begin() as conn:
            weeks_to_score = conn.execute(
                GET_ENDED_WEEKS,
                {"leagueId": league_id, "now": now},
            ).fetchall()

        failed = False
        for row in weeks_to_score:
            week_number = int(row._mapping["weekNumber"])
            week_id = int(row._mapping["id"])

            try:
                scoring_model.compute_weekly_scores(
                    league_id=league_id,
                    week_number=week_number,
                )
            except Exception as e:
                print(f"  ERROR scoring league {league_id} week {week_number}: {e}")
                failed = True
                break

            with engine.begin() as conn:
                conn.execute(MARK_WEEK_SCORED, {"week_id": week_id})
                conn.execute(
                    LOCK_NEXT_WEEK,
                    {"league_id": league_id, "next_week_number": week_number + 1},
                )

        if failed:
            print(f"  Aborted scoring for league {league_id} after error.")
        else:
            print(f"  Finished scoring league {league_id}")


if __name__ == "__main__":
    main()
