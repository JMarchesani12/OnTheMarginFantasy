import argparse
from datetime import datetime, timezone
import os

from dotenv import load_dotenv
from sqlalchemy import text
from endpoints.schedule.scheduleModel import ScheduleModel

from db import engine

INSERT_REGULAR = text("""
    INSERT INTO "SeasonPhase" ("sportSeasonId","tournamentId","type","name","startDate","endDate","priority")
    VALUES (:sportSeasonId, NULL, 'RegularSeason', 'Regular Season', NULL, NULL, 1)
    ON CONFLICT DO NOTHING;
""")

INSERT_MARCH_MADNESS = text("""
    INSERT INTO "SeasonPhase" ("sportSeasonId","tournamentId","type","name","startDate","endDate","priority")
    SELECT
    :sportSeasonId,
    td.id,
    'NationalTournament',
    td.name,
    NULL,
    NULL,
    2
    FROM "TournamentDefinition" td
    WHERE td."sportId" = :sportId
    AND td.code = 'NCAA_TOURNEY'
    LIMIT 1
    ON CONFLICT DO NOTHING;
""")

INSERT_CONF_TOURNEYS = text("""
    INSERT INTO "SeasonPhase" ("sportSeasonId","tournamentId","type","name","startDate","endDate","priority")
    SELECT
    :sportSeasonId,
    td.id AS "tournamentId",
    'ConferenceTournament' AS "type",
    td.name AS "name",
    NULL,
    NULL,
    2
    FROM "SportConference" sc
    JOIN "TournamentDefinition" td
    ON td."sportConferenceId" = sc.id
    WHERE sc."sportId" = :sportId
    AND td.scope = 'Conference'
    ON CONFLICT DO NOTHING;
""")

FIND_UNMATCHED_SPORT_CONFERENCES = text("""
    SELECT sc.id AS "sportConferenceId", sc."conferenceId"
    FROM "SportConference" sc
    LEFT JOIN "TournamentDefinition" td
    ON td."sportConferenceId" = sc.id
    AND td.scope = 'Conference'
    WHERE sc."sportId" = :sportId
    AND td.id IS NULL;
""")

def parse_dt(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    if len(s) == 10:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

    return datetime.fromisoformat(s)


def main():
    load_dotenv()
    espn_base_url = os.getenv("ESPN_BASE_URL")
    if not espn_base_url:
        raise ValueError("Missing ESPN_BASE_URL in .env")

    ap = argparse.ArgumentParser()
    ap.add_argument("--seasonYear", type=int, required=True)
    ap.add_argument("--regularStart", type=str, required=True)
    ap.add_argument("--regularEnd", type=str, required=True)
    ap.add_argument("--playoffStart", type=str, default=None)
    ap.add_argument("--playoffEnd", type=str, default=None)
    args = ap.parse_args()

    regular_start = parse_dt(args.regularStart)
    regular_end = parse_dt(args.regularEnd)
    playoff_start = parse_dt(args.playoffStart) if args.playoffStart else None
    playoff_end = parse_dt(args.playoffEnd) if args.playoffEnd else None

    schedule_model = ScheduleModel(engine, espn_base_url)

    with engine.begin() as conn:

        sport_season_id = schedule_model.upsert_sport_season(
            conn,
            sport_id=1,
            season_year=args.seasonYear,
            regular_start=regular_start,
            regular_end=regular_end,
            playoff_start=playoff_start,
            playoff_end=playoff_end,
        )

        unmatched = conn.execute(FIND_UNMATCHED_SPORT_CONFERENCES, {"sportId": 1}).fetchall()
        if unmatched:
            details = ", ".join([f"(sportConferenceId={r._mapping['sportConferenceId']}, conferenceId={r._mapping['conferenceId']})" for r in unmatched])
            raise ValueError(f"Missing TournamentDefinition for some SportConference rows: {details}")
        
        conn.execute(INSERT_REGULAR, {"sportSeasonId": sport_season_id})
        conn.execute(INSERT_CONF_TOURNEYS, {"sportSeasonId": sport_season_id, "sportId": 1})
        conn.execute(INSERT_MARCH_MADNESS, {"sportSeasonId": sport_season_id, "sportId": 1})

    schedule_model.bootstrap_league_schedule(1, sport_season_id, 5)


if __name__ == "__main__":
    main()


#     PYTHONPATH=./api python3 ./api/startSeasonJobs/ncaaMensBasketball.py \
#   --seasonYear 2025 \
#   --regularStart "2025-11-03" \
#   --regularEnd   "2026-03-08" \
#   --playoffStart "2026-03-09" \
#   --playoffEnd   "2026-04-08" \
