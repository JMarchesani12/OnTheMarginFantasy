import argparse
from datetime import datetime, timezone
import os
import sys

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

def require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"Missing required env var: {name}")
        sys.exit(1)
    return val


def main():
    load_dotenv()
    espn_base_url = require_env("ESPN_BASE_URL")

    season_year = int(require_env("SEASON_YEAR"))
    regular_start_s = require_env("REGULAR_START")
    regular_end_s = require_env("REGULAR_END")
    playoff_start_s = os.getenv("PLAYOFF_START")
    playoff_end_s = os.getenv("PLAYOFF_END")

    regular_start = parse_dt(regular_start_s)
    regular_end = parse_dt(regular_end_s)
    playoff_start = parse_dt(playoff_start_s) if playoff_start_s else None
    playoff_end = parse_dt(playoff_end_s) if playoff_end_s else None

    schedule_model = ScheduleModel(engine, espn_base_url)

    with engine.begin() as conn:

        sport_season_id = schedule_model.upsert_sport_season(
            conn,
            sport_id=1,
            season_year=season_year,
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

    schedule_model.bootstrap_league_schedule(1, sport_season_id)


if __name__ == "__main__":
    main()


# From OnTheMarginFantasy folder
# PYTHONPATH=./api python3 ./api/startSeasonJobs/ncaaMensBasketball.py --seasonYear 2025 --regularStart "2025-11-03" --regularEnd   "2026-03-08" --playoffStart "2026-03-09" --playoffEnd "2026-04-08"
