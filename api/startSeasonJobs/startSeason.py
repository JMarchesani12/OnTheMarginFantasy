import argparse
from dataclasses import dataclass
from datetime import date
import os

from dotenv import load_dotenv
from sqlalchemy import text


@dataclass(frozen=True)
class SportConfig:
    sport_id: int
    has_conference_tournaments: bool = False
    national_tournament_codes: tuple[str, ...] = ()


SPORT_CONFIGS = {
    "ncaa-mens-basketball": SportConfig(
        sport_id=1,
        has_conference_tournaments=True,
        national_tournament_codes=("NCAA_TOURNEY",),
    ),
    "college-football": SportConfig(
        sport_id=2,
        national_tournament_codes=("CFP", "FCS_PLAYOFFS"),
    ),
}

INSERT_REGULAR_PHASE = text("""
    INSERT INTO "SeasonPhase"
        ("sportSeasonId", "tournamentId", "type", "name", "startDate", "endDate", "priority")
    VALUES
        (:sportSeasonId, NULL, 'RegularSeason', 'Regular Season', NULL, NULL, 1)
    ON CONFLICT DO NOTHING;
""")

INSERT_CONFERENCE_PHASES = text("""
    INSERT INTO "SeasonPhase"
        ("sportSeasonId", "tournamentId", "type", "name", "startDate", "endDate", "priority")
    SELECT
        :sportSeasonId,
        td.id,
        'ConferenceTournament',
        td.name,
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

INSERT_NATIONAL_TOURNAMENT_PHASE = text("""
    INSERT INTO "SeasonPhase"
        ("sportSeasonId", "tournamentId", "type", "name", "startDate", "endDate", "priority")
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
      AND td.code = :tournamentCode
    LIMIT 1
    ON CONFLICT DO NOTHING;
""")

FIND_UNMATCHED_CONFERENCES = text("""
    SELECT sc.id AS "sportConferenceId", sc."conferenceId"
    FROM "SportConference" sc
    LEFT JOIN "TournamentDefinition" td
      ON td."sportConferenceId" = sc.id
     AND td.scope = 'Conference'
    WHERE sc."sportId" = :sportId
      AND td.id IS NULL;
""")

FIND_NATIONAL_TOURNAMENT = text("""
    SELECT id
    FROM "TournamentDefinition"
    WHERE "sportId" = :sportId
      AND code = :tournamentCode
    LIMIT 1;
""")


def parse_date(value: str) -> date:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return date.fromisoformat(value if len(value) == 10 else value.split("T")[0])


def arg_or_env(args, arg_name: str, env_name: str, *, required: bool = True):
    value = getattr(args, arg_name)
    if value is None:
        value = os.getenv(env_name)
    if required and value is None:
        raise ValueError(f"Missing required value: --{arg_name.replace('_', '-')} or env {env_name}")
    return value


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value


def configure_season_phases(conn, sport_season_id: int, config: SportConfig) -> None:
    conn.execute(INSERT_REGULAR_PHASE, {"sportSeasonId": sport_season_id})

    if config.has_conference_tournaments:
        unmatched = conn.execute(
            FIND_UNMATCHED_CONFERENCES,
            {"sportId": config.sport_id},
        ).fetchall()
        if unmatched:
            details = ", ".join(
                f"(sportConferenceId={row._mapping['sportConferenceId']}, "
                f"conferenceId={row._mapping['conferenceId']})"
                for row in unmatched
            )
            raise ValueError(
                "Missing TournamentDefinition for some SportConference rows: " + details
            )

        conn.execute(
            INSERT_CONFERENCE_PHASES,
            {
                "sportSeasonId": sport_season_id,
                "sportId": config.sport_id,
            },
        )

    for tournament_code in config.national_tournament_codes:
        tournament_params = {
            "sportId": config.sport_id,
            "tournamentCode": tournament_code,
        }
        if conn.execute(FIND_NATIONAL_TOURNAMENT, tournament_params).first() is None:
            raise ValueError(
                "Missing TournamentDefinition "
                f"for sportId={config.sport_id}, code={tournament_code}"
            )

        conn.execute(
            INSERT_NATIONAL_TOURNAMENT_PHASE,
            {
                **tournament_params,
                "sportSeasonId": sport_season_id,
            },
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Set up and bootstrap a sport season.")
    parser.add_argument("--sport", choices=sorted(SPORT_CONFIGS))
    parser.add_argument("--season-year", "--SEASON_YEAR", dest="season_year", type=int)
    parser.add_argument("--regular-start", "--REGULAR_START", dest="regular_start")
    parser.add_argument("--regular-end", "--REGULAR_END", dest="regular_end")
    parser.add_argument("--playoff-start", "--PLAYOFF_START", dest="playoff_start")
    parser.add_argument("--playoff-end", "--PLAYOFF_END", dest="playoff_end")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bootstrap the schedule even if the season was already bootstrapped.",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        help="Limit schedule bootstrapping to this many days.",
    )
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()

    from db import engine
    from endpoints.schedule.scheduleModel import ScheduleModel

    sport_name = arg_or_env(args, "sport", "SPORT")
    config = SPORT_CONFIGS.get(sport_name)
    if config is None:
        supported = ", ".join(sorted(SPORT_CONFIGS))
        raise ValueError(f"Unsupported sport {sport_name!r}. Choose one of: {supported}")

    season_year = int(arg_or_env(args, "season_year", "SEASON_YEAR"))
    regular_start = parse_date(arg_or_env(args, "regular_start", "REGULAR_START"))
    regular_end = parse_date(arg_or_env(args, "regular_end", "REGULAR_END"))
    playoff_start_value = arg_or_env(
        args, "playoff_start", "PLAYOFF_START", required=False
    )
    playoff_end_value = arg_or_env(args, "playoff_end", "PLAYOFF_END", required=False)
    playoff_start = parse_date(playoff_start_value) if playoff_start_value else None
    playoff_end = parse_date(playoff_end_value) if playoff_end_value else None

    if (playoff_start is None) != (playoff_end is None):
        raise ValueError("PLAYOFF_START and PLAYOFF_END must be provided together")
    if regular_end < regular_start:
        raise ValueError("REGULAR_END cannot be before REGULAR_START")
    if playoff_start and playoff_end and playoff_end < playoff_start:
        raise ValueError("PLAYOFF_END cannot be before PLAYOFF_START")

    schedule_model = ScheduleModel(engine, require_env("ESPN_BASE_URL"))

    with engine.begin() as conn:
        sport_season_id = schedule_model.upsert_sport_season(
            conn,
            sport_id=config.sport_id,
            season_year=season_year,
            regular_start=regular_start,
            regular_end=regular_end,
            playoff_start=playoff_start,
            playoff_end=playoff_end,
        )
        configure_season_phases(conn, sport_season_id, config)

    summary = schedule_model.bootstrap_sport_season_schedule_by_scoreboard(
        sport_season_id,
        force=args.force,
        max_days=args.max_days,
    )
    print(summary)


if __name__ == "__main__":
    main()
