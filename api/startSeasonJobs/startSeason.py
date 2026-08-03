"""Create a sport season, its subdivision windows, phases, and ESPN schedule.

Run from the api directory after confirming the dates in the JSON manifest:

    PYTHONPATH=. python3 startSeasonJobs/startSeason.py \
        --config startSeasonJobs/configs/college-football-2026.json

Use ``--max-days 3`` for a limited ingestion test. Use ``--force`` to ingest a
season again after it has already been marked as bootstrapped.
"""

import argparse
from dataclasses import dataclass
from datetime import date
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import text


@dataclass(frozen=True)
class SportConfig:
    """Stable behavior associated with a sport, independent of season dates."""

    sport_id: int
    has_conference_tournaments: bool = False
    national_tournament_codes: tuple[str, ...] = ()
    required_subdivision_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SubdivisionSeasonConfig:
    """One subdivision's regular-season and postseason windows."""

    code: str
    name: str
    regular_start: date
    regular_end: date
    postseason_start: date | None = None
    postseason_end: date | None = None


@dataclass(frozen=True)
class SeasonManifest:
    """Validated contents of a season JSON manifest."""

    sport: str
    season_year: int
    season_start: date
    season_end: date
    subdivisions: tuple[SubdivisionSeasonConfig, ...]


SPORT_CONFIGS = {
    # Basketball discovers all conference tournaments from TournamentDefinition.
    "ncaa-mens-basketball": SportConfig(
        sport_id=1,
        has_conference_tournaments=True,
        national_tournament_codes=("NCAA_TOURNEY",),
        required_subdivision_codes=("D1",),
    ),
    "college-football": SportConfig(
        sport_id=2,
        national_tournament_codes=("FBS_PLAYOFFS", "FCS_PLAYOFFS"),
        required_subdivision_codes=("FBS", "FCS"),
    ),
}

# SeasonPhase types are fixed by the scoring model. Tournament definitions
# provide the sport-specific names and identities attached to those phases.
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

UPSERT_SPORT_SEASON_SUBDIVISION = text("""
    INSERT INTO "SportSeasonSubdivision" (
        "sportSeasonId",
        code,
        name,
        "regularSeasonStart",
        "regularSeasonEnd",
        "postseasonStart",
        "postseasonEnd"
    )
    VALUES (
        :sportSeasonId,
        :code,
        :name,
        :regularSeasonStart,
        :regularSeasonEnd,
        :postseasonStart,
        :postseasonEnd
    )
    ON CONFLICT ("sportSeasonId", code)
    DO UPDATE SET
        name = EXCLUDED.name,
        "regularSeasonStart" = EXCLUDED."regularSeasonStart",
        "regularSeasonEnd" = EXCLUDED."regularSeasonEnd",
        "postseasonStart" = EXCLUDED."postseasonStart",
        "postseasonEnd" = EXCLUDED."postseasonEnd"
    RETURNING id;
""")


def parse_date(value: str) -> date:
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return date.fromisoformat(value if len(value) == 10 else value.split("T")[0])


def required_string(data: dict[str, Any], key: str, context: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def optional_manifest_date(
    data: dict[str, Any],
    key: str,
    context: str,
) -> date | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{context}.{key} must be an ISO date string or null")
    return parse_date(value)


def load_manifest(path: Path) -> SeasonManifest:
    """Load and validate all season-specific input before writing anything."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Season config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in season config {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Season config must contain a JSON object")

    sport = required_string(raw, "sport", "config")
    season_year = raw.get("seasonYear")
    if not isinstance(season_year, int) or isinstance(season_year, bool):
        raise ValueError("config.seasonYear must be an integer")

    season_start = parse_date(required_string(raw, "seasonStart", "config"))
    season_end = parse_date(required_string(raw, "seasonEnd", "config"))
    if season_end < season_start:
        raise ValueError("config.seasonEnd cannot be before config.seasonStart")

    raw_subdivisions = raw.get("subdivisions")
    if not isinstance(raw_subdivisions, list) or not raw_subdivisions:
        raise ValueError("config.subdivisions must be a non-empty array")

    subdivisions = []
    seen_codes = set()
    for index, item in enumerate(raw_subdivisions):
        context = f"config.subdivisions[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{context} must be an object")

        code = required_string(item, "code", context).upper()
        if code in seen_codes:
            raise ValueError(f"Duplicate subdivision code: {code}")
        seen_codes.add(code)

        regular_start = parse_date(required_string(item, "regularSeasonStart", context))
        regular_end = parse_date(required_string(item, "regularSeasonEnd", context))
        postseason_start = optional_manifest_date(item, "postseasonStart", context)
        postseason_end = optional_manifest_date(item, "postseasonEnd", context)

        if regular_end < regular_start:
            raise ValueError(f"{context}.regularSeasonEnd cannot be before its start")
        if (postseason_start is None) != (postseason_end is None):
            raise ValueError(
                f"{context}.postseasonStart and postseasonEnd must be provided together"
            )
        if postseason_start and postseason_end and postseason_end < postseason_start:
            raise ValueError(f"{context}.postseasonEnd cannot be before its start")

        subdivision_start = min(
            value for value in (regular_start, postseason_start) if value is not None
        )
        subdivision_end = max(
            value for value in (regular_end, postseason_end) if value is not None
        )
        if subdivision_start < season_start or subdivision_end > season_end:
            raise ValueError(
                f"{context} dates must fit inside config.seasonStart/config.seasonEnd"
            )

        subdivisions.append(
            SubdivisionSeasonConfig(
                code=code,
                name=required_string(item, "name", context),
                regular_start=regular_start,
                regular_end=regular_end,
                postseason_start=postseason_start,
                postseason_end=postseason_end,
            )
        )

    return SeasonManifest(
        sport=sport,
        season_year=season_year,
        season_start=season_start,
        season_end=season_end,
        subdivisions=tuple(subdivisions),
    )


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
    """Create the regular, conference, and configured national phases."""

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


def upsert_subdivision_seasons(
    conn,
    sport_season_id: int,
    subdivisions: tuple[SubdivisionSeasonConfig, ...],
) -> list[int]:
    """Insert or refresh each subdivision window from the manifest."""

    subdivision_ids = []
    for subdivision in subdivisions:
        row = conn.execute(
            UPSERT_SPORT_SEASON_SUBDIVISION,
            {
                "sportSeasonId": sport_season_id,
                "code": subdivision.code,
                "name": subdivision.name,
                "regularSeasonStart": subdivision.regular_start,
                "regularSeasonEnd": subdivision.regular_end,
                "postseasonStart": subdivision.postseason_start,
                "postseasonEnd": subdivision.postseason_end,
            },
        ).first()
        subdivision_ids.append(int(row[0]))
    return subdivision_ids


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Set up and bootstrap a sport season.")
    parser.add_argument(
        "--config",
        help="Path to a JSON season manifest (or set SEASON_CONFIG).",
    )
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

    config_path = Path(arg_or_env(args, "config", "SEASON_CONFIG")).expanduser()
    manifest = load_manifest(config_path)

    config = SPORT_CONFIGS.get(manifest.sport)
    if config is None:
        supported = ", ".join(sorted(SPORT_CONFIGS))
        raise ValueError(f"Unsupported sport {manifest.sport!r}. Choose one of: {supported}")

    subdivision_codes = {subdivision.code for subdivision in manifest.subdivisions}
    missing_codes = set(config.required_subdivision_codes) - subdivision_codes
    if missing_codes:
        raise ValueError(
            f"Missing required subdivisions for {manifest.sport}: "
            + ", ".join(sorted(missing_codes))
        )

    from db import engine
    from endpoints.schedule.scheduleModel import ScheduleModel

    schedule_model = ScheduleModel(engine, require_env("ESPN_BASE_URL"))

    # Keep the season, subdivision windows, and phases atomic. A validation or
    # database failure rolls the entire setup transaction back.
    with engine.begin() as conn:
        sport_season_id = schedule_model.upsert_sport_season(
            conn,
            sport_id=config.sport_id,
            season_year=manifest.season_year,
            season_start=manifest.season_start,
            season_end=manifest.season_end,
        )
        subdivision_ids = upsert_subdivision_seasons(
            conn,
            sport_season_id,
            manifest.subdivisions,
        )
        configure_season_phases(conn, sport_season_id, config)

    # ESPN calls happen after the metadata transaction so a long bootstrap does
    # not hold database locks for the full ingestion window.
    summary = schedule_model.bootstrap_sport_season_schedule_by_scoreboard(
        sport_season_id,
        force=args.force,
        max_days=args.max_days,
    )
    summary["subdivisionSeasonIds"] = subdivision_ids
    print(summary)


if __name__ == "__main__":
    main()


# For Casey: During the playoff season, only give points to the winner, do not subtract points for the loser.
# Currently the implementation is no points are awarded (I think)