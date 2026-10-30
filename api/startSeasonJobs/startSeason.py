"""Create a sport season, its subdivision windows, phases, and ESPN schedule.

Run from the api directory after confirming the dates in the JSON manifest:

    PYTHONPATH=. python3 startSeasonJobs/startSeason.py \
        --config startSeasonJobs/configs/college-football-2026.json

Use ``--max-days 3`` for a limited ingestion test. Use ``--force`` to ingest a
season again after it has already been marked as bootstrapped.
"""

import argparse
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import json
import os
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from sqlalchemy import text


@dataclass(frozen=True)
class SportConfig:
    """Stable behavior associated with a sport, independent of season dates."""

    sport_id: int
    has_conference_tournaments: bool = False
    national_tournament_codes: tuple[str, ...] = ()
    required_subdivision_codes: tuple[str, ...] = ()
    uses_tournament_manifest: bool = False


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
    tournaments: tuple[dict[str, Any], ...] = ()
    timezone: str = "UTC"


SPORT_CONFIGS = {
    # Basketball uses explicit dated tournaments in its manifest.
    "ncaa-mens-basketball": SportConfig(
        sport_id=1,
        has_conference_tournaments=True,
        national_tournament_codes=("NCAA_TOURNEY", "NIT", "CBI", "CROWN"),
        uses_tournament_manifest=True,
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

    timezone_name = raw.get("timezone", "UTC")
    try:
        if not isinstance(timezone_name, str):
            raise ValueError("timezone must be a string")
        ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("config.timezone must be an IANA timezone name") from exc
    tournaments = raw.get("tournaments", [])
    if not isinstance(tournaments, list):
        raise ValueError("config.tournaments must be an array")
    seen_tournaments = set()
    for i, tournament in enumerate(tournaments):
        context = f"config.tournaments[{i}]"
        if not isinstance(tournament, dict):
            raise ValueError(f"{context} must be an object")
        code = required_string(tournament, "code", context)
        if code in seen_tournaments:
            raise ValueError(f"Duplicate tournament code: {code}")
        seen_tournaments.add(code)
        required_string(tournament, "name", context)
        if tournament.get("scope") not in ("Conference", "National"):
            raise ValueError(f"{context}.scope must be Conference or National")
        conference_id = tournament.get("sportConferenceId")
        if tournament["scope"] == "Conference":
            if not isinstance(conference_id, int) or isinstance(conference_id, bool) or conference_id <= 0:
                raise ValueError(f"{context}.sportConferenceId must be a positive integer")
        elif conference_id is not None:
            raise ValueError(f"{context}: national tournaments cannot have sportConferenceId")
        start = parse_date(required_string(tournament, "startDate", context))
        end = parse_date(required_string(tournament, "endDate", context))
        if not season_start <= start <= end <= season_end:
            raise ValueError(f"{context} dates must be ordered and inside the season")
        rules = tournament.setdefault("rules", {})
        if not isinstance(rules, dict):
            raise ValueError(f"{context}.rules must be an object")
        if set(rules) - {"positiveOnly", "marginMultiplier", "scoringPeriod", "primaryPostseason", "sourceLabels", "sourceIds", "eventIds"}:
            raise ValueError(f"{context}.rules contains unknown keys")
        for key in ("positiveOnly", "primaryPostseason"):
            if key in rules and not isinstance(rules[key], bool):
                raise ValueError(f"{context}.rules.{key} must be boolean")
        multiplier = rules.get("marginMultiplier", 1)
        if isinstance(multiplier, bool) or not isinstance(multiplier, (int, float)) or multiplier not in (0.5, 1, 2):
            raise ValueError(f"{context}.rules.marginMultiplier must be 0.5, 1 or 2")
        if rules.get("scoringPeriod") not in (None, "BASKETBALL_FINAL"):
            raise ValueError(f"{context}.rules.scoringPeriod must be BASKETBALL_FINAL or null")
        for key in ("sourceLabels", "sourceIds", "eventIds"):
            values = rules.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f"{context}.rules.{key} must be an array of nonempty strings")
        if not any(rules.get(key) for key in ("sourceLabels", "sourceIds", "eventIds")):
            raise ValueError(f"{context} requires sourceLabels, sourceIds or eventIds")

    return SeasonManifest(
        sport=sport,
        season_year=season_year,
        season_start=season_start,
        season_end=season_end,
        subdivisions=tuple(subdivisions),
        tournaments=tuple(tournaments),
        timezone=timezone_name,
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


def configure_manifest_phases(conn, sport_season_id, config, manifest):
    """Upsert explicit dated tournament instances; no blanket conference discovery."""
    required = set(config.national_tournament_codes)
    if not required.issubset({t["code"] for t in manifest.tournaments}):
        raise ValueError("Basketball config requires NCAA_TOURNEY, NIT, CBI and CROWN tournaments")
    configured_conferences = {t.get("sportConferenceId") for t in manifest.tournaments}
    conferences = conn.execute(text('''
        SELECT id FROM "SportConference" WHERE "sportId"=:sport
    '''), {"sport": config.sport_id}).fetchall()
    missing = {int(row[0]) for row in conferences} - configured_conferences
    if missing:
        raise ValueError("Add dated conference tournament config entries for basketball SportConference IDs: "
                         + ", ".join(map(str, sorted(missing))))
    season_tz = ZoneInfo(manifest.timezone)
    start = datetime.combine(manifest.season_start, time.min, season_tz)
    end = datetime.combine(manifest.season_end + timedelta(days=1), time.min, season_tz)
    regular_params = {"start": start, "end": end, "season": sport_season_id}
    regular = conn.execute(text('''
        UPDATE "SeasonPhase" SET "startDate"=:start, "endDate"=:end
        WHERE "sportSeasonId"=:season AND type='RegularSeason' RETURNING id
    '''), regular_params).first()
    if not regular:
        conn.execute(text('''
            INSERT INTO "SeasonPhase" ("sportSeasonId", "tournamentId", type, name,
                "startDate", "endDate", priority)
            VALUES (:season, NULL, 'RegularSeason', 'Regular Season', :start, :end, 1)
        '''), regular_params)
    for tournament in manifest.tournaments:
        conference_id = tournament.get("sportConferenceId")
        if conference_id is not None and conn.execute(text('''
            SELECT id FROM "SportConference" WHERE id=:id AND "sportId"=:sport
        '''), {"id": conference_id, "sport": config.sport_id}).first() is None:
            raise ValueError(f"Invalid basketball sportConferenceId: {conference_id}")
        params = {"sport": config.sport_id, "code": tournament["code"],
                  "name": tournament["name"], "scope": tournament["scope"], "conference": conference_id}
        existing = conn.execute(text('''
            SELECT id, scope, "sportConferenceId" FROM "TournamentDefinition"
            WHERE "sportId"=:sport AND code=:code
        '''), params).mappings().first()
        if existing:
            if existing['scope'] != params['scope'] or existing['sportConferenceId'] != conference_id:
                raise ValueError(f"Tournament identity conflicts for {tournament['code']}")
            tournament_id = existing['id']
            conn.execute(text('UPDATE "TournamentDefinition" SET name=:name WHERE id=:id'),
                         {"name": tournament["name"], "id": tournament_id})
        else:
            tournament_id = conn.execute(text('''
                INSERT INTO "TournamentDefinition" ("sportId", code, name, scope, "sportConferenceId")
                VALUES (:sport, :code, :name, :scope, :conference) RETURNING id
            '''), params).scalar_one()
        rules = {"positiveOnly": True, "marginMultiplier": 1, "primaryPostseason": False}
        rules.update(tournament.get("rules", {}))
        rules["timezone"] = manifest.timezone
        phase_params = {
            "season": sport_season_id, "tournament": tournament_id,
            "type": "ConferenceTournament" if conference_id is not None else "NationalTournament",
            "name": tournament["name"], "rules": json.dumps(rules),
            "start": datetime.combine(parse_date(tournament["startDate"]), time.min, season_tz),
            "end": datetime.combine(parse_date(tournament["endDate"]) + timedelta(days=1), time.min, season_tz),
        }
        # Update before insert so reruns repair existing NULL dates and rules.
        found = conn.execute(text('''
            UPDATE "SeasonPhase" SET "startDate"=:start, "endDate"=:end,
                name=:name, type=:type, rules=CAST(:rules AS jsonb)
            WHERE "sportSeasonId"=:season AND "tournamentId"=:tournament RETURNING id
        '''), phase_params).first()
        if not found:
            conn.execute(text('''
                INSERT INTO "SeasonPhase" ("sportSeasonId", "tournamentId", type, name,
                    "startDate", "endDate", priority, rules)
                VALUES (:season, :tournament, :type, :name, :start, :end, 2, CAST(:rules AS jsonb))
            '''), phase_params)


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
        help="Discard resume checkpoints and refresh all dates, even for a completed season.",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        help="Process at most this many pending dates; later runs resume the next batch.",
    )
    parser.add_argument(
        "--checkpoint-file",
        help="Override the local resume checkpoint file (defaults to api/.cache/season-bootstrap/).",
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
    from endpoints.schedule.ingestion_service import ScheduleIngestionService

    schedule_model = ScheduleIngestionService(engine, require_env("ESPN_BASE_URL"))

    # Keep the season, subdivision windows, and phases atomic. A validation or
    # database failure rolls the entire setup transaction back.
    with engine.begin() as conn:
        sport_season_id = schedule_model.upsert_season_for_job(
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
        if config.uses_tournament_manifest:
            configure_manifest_phases(conn, sport_season_id, config, manifest)
        else:
            configure_season_phases(conn, sport_season_id, config)

    # ESPN calls happen after the metadata transaction so a long bootstrap does
    # not hold database locks for the full ingestion window.
    summary = schedule_model.bootstrap_for_job(
        sport_season_id,
        force=args.force,
        max_days=args.max_days,
        checkpoint_path=args.checkpoint_file,
    )
    summary["subdivisionSeasonIds"] = subdivision_ids
    print(summary)
    if summary.get("failedDays", 0):
        raise RuntimeError("Schedule ingestion was incomplete; fix reported errors and rerun")


if __name__ == "__main__":
    main()
