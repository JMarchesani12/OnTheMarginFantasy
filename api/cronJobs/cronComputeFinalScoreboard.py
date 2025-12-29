from bootstrap import *
import os
from db import engine
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import text

from endpoints.schedule.scheduleModel import ScheduleModel
from endpoints.scoring.scoringEndpoints import ScoringEndpoints


def build_scoring(engine):
    load_dotenv()
    espn_base_url = os.getenv("ESPN_BASE_URL")
    schedule_model = ScheduleModel(engine, espn_base_url)
    scoring = ScoringEndpoints(engine, schedule_model)
    return scoring


def main():
    scoring = build_scoring(engine)
    now = datetime.now(timezone.utc)

    # 1. Find SportSeasons whose playoffEnd has passed,
    #    and that we haven't finalized yet.
    #
    # You may want a flag on SportSeason or League, e.g. "seasonFinalized".
    # Here I’ll assume a boolean "seasonFinalized" on SportSeason.
    with engine.begin() as conn:
        sport_seasons = conn.execute(
            text(
                """
                SELECT
                    ss.id          AS "sportSeasonId",
                    ss."sportId"   AS "sportId",
                    ss."seasonYear" AS "seasonYear"
                FROM "SportSeason" ss
                WHERE ss."playoffEnd" IS NOT NULL
                  AND ss."playoffEnd" <= :now
                  AND COALESCE(ss."seasonFinalized", FALSE) = FALSE
                """
            ),
            {"now": now},
        ).fetchall()

    if not sport_seasons:
        print("No SportSeasons ready for finalization.")
        return

    for ss in sport_seasons:
        sport_season_id = int(ss._mapping["sportSeasonId"])
        sport_id = int(ss._mapping["sportId"])
        season_year = int(ss._mapping["seasonYear"])

        print(
            f"Finalizing SportSeason {sport_season_id} "
            f"(sportId={sport_id}, seasonYear={season_year})"
        )

        # 2. Find all leagues that belong to this sport + seasonYear
        with engine.begin() as conn:
            leagues = conn.execute(
                text(
                    """
                    SELECT l.id AS "leagueId"
                    FROM "League" l
                    WHERE l."sport" = :sport_id
                      AND l."seasonYear" = :season_year
                    """
                ),
                {"sport_id": sport_id, "season_year": season_year},
            ).fetchall()

        for row in leagues:
            league_id = int(row._mapping["leagueId"])
            print(f"  Computing end-of-year standings for league {league_id}")
            scoring.compute_end_of_year_season_standings(league_id)
            
            with engine.begin() as conn:
                conn.execute(
                    text(
                        """
                        UPDATE "League"
                        SET "status" = 'Completed
                        WHERE id = :league_id
                        """
                    ),
                    {"league_id": league_id},
                )

        # 3. Mark SportSeason as finalized
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE "SportSeason"
                       SET "seasonFinalized" = TRUE
                     WHERE id = :sport_season_id
                    """
                ),
                {"sport_season_id": sport_season_id},
            )

    print("Season finalization complete.")


if __name__ == "__main__":
    main()
