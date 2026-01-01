import datetime as dt
import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import Tuple, text
from sqlalchemy.engine import Engine

from endpoints.schedule.helpers.espn.espnClient import ESPNClient
from endpoints.schedule.helpers.weekHelper import compute_weeks_from_start

logger = logging.getLogger(__name__)


class ScheduleModel:
    """
    Handles:
      - Season/week setup for a league (using SportSeason + League.settings)
      - Global GameResult ingestion for a sport-season:
          * via team schedules (/teams/{id}/schedule)
          * via daily scoreboard (/scoreboard?dates=YYYYMMDD)
    """

    def __init__(self, db: Engine, espn_base_url: str) -> None:
        self.db = db
        self.espn_base_url = espn_base_url.rstrip("/")

    # -------------------------------------------------------------------------
    # Basic lookups
    # -------------------------------------------------------------------------

    def _get_league(self, league_id: int) -> Dict[str, Any]:
        sql = text("""
            SELECT id, "sport", "seasonYear", settings
            FROM "League"
            WHERE id = :leagueId
        """)
        with self.db.begin() as conn:
            row = conn.execute(sql, {"leagueId": league_id}).fetchone()

        if not row:
            raise ValueError(f"League {league_id} not found")

        return dict(row._mapping)

    def _get_league_settings(self, league_id: int) -> Dict[str, Any]:
        league = self._get_league(league_id)
        settings = league.get("settings") or {}
        if isinstance(settings, str):
            settings = json.loads(settings)
        return settings or {}

    def _get_sport_season_for_league(self, league_id: int) -> Dict[str, Any]: 
        sql = text(""" 
                SELECT 
                   ss.id AS "sportSeasonId", 
                   ss."sportId", ss."seasonYear", 
                   ss."regularSeasonStart", 
                   ss."regularSeasonEnd", 
                   ss."playoffStart", 
                   ss."playoffEnd", 
                   ss."scheduleBootstrapped", 
                   ss."scheduleBootstrappedAt" 
                FROM "League" l 
                JOIN "SportSeason" ss 
                ON ss."sportId" = l."sport" 
                AND ss."seasonYear" = l."seasonYear" 
                WHERE l.id = :leagueId LIMIT 1 
            """
        ) 
        
        with self.db.begin() as conn: 
            row = conn.execute(sql, {"leagueId": league_id}).fetchone() 
            
        if not row: 
            raise ValueError( "No SportSeason found for this league's sport + seasonYear. " "Make sure SportSeason exists." ) 
        
        return dict(row._mapping)

    def _get_sport_api_config(self, sport_id: int) -> Tuple[str, List[int]]:
        """
        Returns (api_keyword, api_group_ids)

        Assumes your Sport table has *two* columns, e.g.:
        - "apiKeyword"  (text)
        - "apiGroupIds"
        """
        sql = text('SELECT "api-keyword", "apiGroupIds", "baseUrlName" FROM "Sport" WHERE id = :sportId')
        with self.db.begin() as conn:
            row = conn.execute(sql, {"sportId": sport_id}).fetchone()

        if not row or row[0] is None:
            raise ValueError(f"Sport {sport_id} missing apiKeyword")

        api_keyword = row[0]
        raw_groups = row[1]
        base_url = row[2]

        # Normalize apiGroupIds into List[int]
        group_ids: List[int] = []
        if raw_groups is None:
            group_ids = []
        elif isinstance(raw_groups, list):
            group_ids = [int(x) for x in raw_groups]
        elif isinstance(raw_groups, str):
            s = raw_groups.strip()
            # could be JSON like "[50,55]" or comma string like "50,55"
            if s.startswith("["):
                group_ids = [int(x) for x in json.loads(s)]
            else:
                group_ids = [int(x.strip()) for x in s.split(",") if x.strip()]
        else:
            # e.g. psycopg may return tuples for int[]
            group_ids = [int(x) for x in raw_groups]

        return api_keyword, group_ids, base_url

    # -------------------------------------------------------------------------
    # Week generation (regular + optional postseason)
    # -------------------------------------------------------------------------

    def _get_existing_weeks(self, league_id: int) -> List[Dict[str, Any]]:
        sql = text("""
            SELECT id, "weekNumber", "startDate", "endDate"
            FROM "Week"
            WHERE "leagueId" = :leagueId
            ORDER BY "weekNumber" ASC
        """)
        with self.db.begin() as conn:
            rows = conn.execute(sql, {"leagueId": league_id}).fetchall()
        return [dict(r._mapping) for r in rows]

    def _insert_week0(self, league_id: int, end_dt) -> Dict[str, Any]:
        with self.db.begin() as conn:
            row = conn.execute(
                text("""
                    insert into "Week" ("leagueId","weekNumber","startDate","endDate","isLocked","scoringComplete")
                    values (:leagueId, 0, null, :endDate, true, false)
                    returning id, "leagueId", "weekNumber", "startDate", "endDate", "isLocked", "scoringComplete"
                """),
                {"leagueId": league_id, "endDate": end_dt},
            ).mappings().first()
        return dict(row)

    
    def _insert_weeks(
        self,
        league_id: int,
        weeks: List[tuple[dt.date, dt.date]],
        starting_week_number: int = 1,
    ) -> List[Dict[str, Any]]:
        if not weeks:
            return []

        sql = text("""
            INSERT INTO "Week"
                ("leagueId", "weekNumber", "startDate", "endDate", "isLocked", "scoringComplete")
            VALUES
                (:leagueId, :weekNumber, :startDate, :endDate, false, false)
            RETURNING id, "weekNumber", "startDate", "endDate"
        """)

        created: List[Dict[str, Any]] = []

        with self.db.begin() as conn:
            for idx, (start_d, end_d) in enumerate(weeks, start=starting_week_number):
                start_dt = dt.datetime.combine(start_d, dt.time.min, tzinfo=dt.timezone.utc)
                end_dt = dt.datetime.combine(end_d, dt.time.max, tzinfo=dt.timezone.utc)

                row = conn.execute(
                    sql,
                    {
                        "leagueId": league_id,
                        "weekNumber": idx,
                        "startDate": start_dt,
                        "endDate": end_dt,
                    },
                ).fetchone()
                created.append(dict(row._mapping))

        logger.debug(
            "Inserted %d weeks for league %s (starting_week_number=%s)",
            len(created), league_id, starting_week_number
        )
        return created

    def ensure_weeks_for_league(self, league_id: int) -> List[Dict[str, Any]]:
        """
        If Week rows already exist for this league, returns them.

        Otherwise:
          - Uses SportSeason regularSeasonStart/End to build regular-season weeks:
              Week 1: regStart → upcoming Sunday (may be partial)
              Week 2+: Monday → Sunday through regEnd
          - If League.settings.schedule.includePostseason is true AND
            SportSeason has playoffStart/playoffEnd, continues numbering into
            postseason weeks.
        """
        existing = self._get_existing_weeks(league_id)
        if existing:
            return existing

        season = self._get_sport_season_for_league(league_id)

        # Regular season weeks
        reg_start_dt = season["regularSeasonStart"]
        reg_end_dt = season["regularSeasonEnd"]
        reg_start_date = reg_start_dt.date()
        reg_end_date = reg_end_dt.date()

        created_all: List[Dict[str, Any]] = []
        created_all.append(self._insert_week0(league_id, reg_start_dt - dt.timedelta(days=1)))

        regular_week_ranges = compute_weeks_from_start(reg_start_date, reg_end_date)
        created_regular = self._insert_weeks(league_id, regular_week_ranges, starting_week_number=1)
        created_all.extend(created_regular)

        # Postseason weeks
        if season.get("playoffStart") and season.get("playoffEnd"):
            playoff_start_dt = season["playoffStart"]
            playoff_end_dt = season["playoffEnd"]
            playoff_start_date = playoff_start_dt.date()
            playoff_end_date = playoff_end_dt.date()

            playoff_ranges = compute_weeks_from_start(playoff_start_date, playoff_end_date)
            last_regular_week = created_regular[-1]["weekNumber"] if created_regular else 0

            created_playoff = self._insert_weeks(
                league_id,
                playoff_ranges,
                starting_week_number=last_regular_week + 1,
            )
            created_all.extend(created_playoff)

        logger.info(
            "ensure_weeks_for_league created %d weeks for league %s",
            len(created_all), league_id,
        )
        return created_all

    def get_weeks_for_league(self, league_id: int) -> List[Dict[str, Any]]:
        return self._get_existing_weeks(league_id)

    # -------------------------------------------------------------------------
    # Global GameResult helpers
    # -------------------------------------------------------------------------

    def _lookup_sport_team_id(self, sport_id: int, espn_team_id: str) -> Optional[int]:
        sql = text("""
            SELECT id
            FROM "SportTeam"
            WHERE "sportId" = :sportId
              AND "externalId" = :externalId
            LIMIT 1
        """)
        with self.db.begin() as conn:
            row = conn.execute(sql, {"sportId": sport_id, "externalId": espn_team_id}).fetchone()
        return int(row[0]) if row else None

    def _insert_or_update_game(
        self,
        sport_id: int,
        sport_season_id: int,
        game: Dict[str, Any],
    ) -> int:
        external_game_id = str(game["externalGameId"])
        event_dt: dt.datetime = game["date"]

        home_team_id = self._lookup_sport_team_id(sport_id, game["homeEspnId"])
        away_team_id = self._lookup_sport_team_id(sport_id, game["awayEspnId"])

        season_phase_id = self._lookup_season_phase_id_for_game(
            sport_season_id,
            event_dt,
        )

        upsert_sql = text("""
            INSERT INTO "GameResult" (
                sport,
                "sportSeasonId",
                "seasonPhaseId",
                "externalGameId",
                date,
                "homeTeamId",
                "awayTeamId",
                "homeScore",
                "awayScore",
                "homeTeamExternalId",
                "awayTeamExternalId",
                "homeTeamName",
                "awayTeamName",
                "broadcast"
            )
            VALUES (
                :sport,
                :sportSeasonId,
                :seasonPhaseId,
                :externalGameId,
                :date,
                :homeTeamId,
                :awayTeamId,
                :homeScore,
                :awayScore,
                :homeTeamExternalId,
                :awayTeamExternalId,
                :homeTeamName,
                :awayTeamName,
                :broadcast
            )
            ON CONFLICT (sport, "sportSeasonId", "externalGameId")
            DO UPDATE SET
                "seasonPhaseId" = EXCLUDED."seasonPhaseId",
                date = EXCLUDED.date,
                "homeTeamId" = EXCLUDED."homeTeamId",
                "awayTeamId" = EXCLUDED."awayTeamId",
                "homeScore" = EXCLUDED."homeScore",
                "awayScore" = EXCLUDED."awayScore",
                "homeTeamExternalId" = EXCLUDED."homeTeamExternalId",
                "awayTeamExternalId" = EXCLUDED."awayTeamExternalId",
                "homeTeamName" = EXCLUDED."homeTeamName",
                "awayTeamName" = EXCLUDED."awayTeamName",
                "broadcast" = EXCLUDED."broadcast"
            RETURNING id;
        """)

        params = {
            "sport": sport_id,
            "sportSeasonId": sport_season_id,
            "seasonPhaseId": season_phase_id,
            "externalGameId": external_game_id,
            "date": event_dt,
            "homeTeamId": home_team_id,
            "awayTeamId": away_team_id,
            "homeScore": game["homeScore"],
            "awayScore": game["awayScore"],
            "homeTeamExternalId": str(game["homeEspnId"]),
            "awayTeamExternalId": str(game["awayEspnId"]),
            "homeTeamName": game["homeName"],
            "awayTeamName": game["awayName"],
            "broadcast": game["broadcast"]
        }

        with self.db.begin() as conn:
            row = conn.execute(upsert_sql, params).fetchone()

        return int(row[0])

    # -------------------------------------------------------------------------
    # Bootstrapping sport-season games (via a league)
    # -------------------------------------------------------------------------

    def _get_all_sport_teams(self, sport_id: int, max_teams: Optional[int] = None) -> List[Dict[str, Any]]:
        base_sql = """
            SELECT id, "sportId", "displayName", "externalId"
            FROM "SportTeam"
            WHERE "sportId" = :sportId
              AND "externalId" IS NOT NULL
            ORDER BY id
        """
        if max_teams is not None:
            base_sql += " LIMIT :maxTeams"

        sql = text(base_sql)
        params: Dict[str, Any] = {"sportId": sport_id}
        if max_teams is not None:
            params["maxTeams"] = max_teams

        with self.db.begin() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [dict(r._mapping) for r in rows]

    def bootstrap_league_schedule(
        self,
        sport_id: int,
        sport_season_id: int,
        max_teams: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        - Ensures Week rows for this league (regular + postseason)
        - If SportSeason.scheduleBootstrapped is false OR force=True:
            * Calls /teams/{id}/schedule for all SportTeams in this sport
            * Inserts games into global GameResult
            * Marks SportSeason.scheduleBootstrapped = true
        Otherwise:
            * Skips the heavy ESPN work and just returns a summary.
        """
        api_keyword, api_group_ids, base_url = self._get_sport_api_config(sport_id)

        teams = self._get_all_sport_teams(sport_id, max_teams=max_teams)
        client = ESPNClient(self.espn_base_url, api_keyword)

        for t in teams:
            external_id = t["externalId"]
            if not external_id:
                continue

            try:
                schedule_json = client.fetch_team_schedule(str(external_id))
            except Exception as e:
                logger.warning("Failed to fetch schedule for team %s: %s", external_id, e)
                continue

            for event in client.iter_team_events(schedule_json):
                game = client.extract_game_from_event(event)
                if not game:
                    continue

                self._insert_or_update_game(sport_id, sport_season_id, game)

        # Mark SportSeason as bootstrapped
        update_sql = text("""
            UPDATE "SportSeason"
            SET "scheduleBootstrapped" = true,
                "scheduleBootstrappedAt" = now()
            WHERE id = :sportSeasonId
        """)
        with self.db.begin() as conn:
            conn.execute(update_sql, {"sportSeasonId": sport_season_id})

        return {
            "sportId": sport_id,
            "sportSeasonId": sport_season_id,
            "teamsProcessed": len(teams),
        }

    # -------------------------------------------------------------------------
    # Scoreboard ingestion (for cron)
    # -------------------------------------------------------------------------

    def ingest_scoreboard_for_date_for_league(
        self,
        league_id: int,
        target_date: dt.date,
    ) -> Dict[str, Any]:
        """
        Convenience wrapper: use league to determine sportSeason and ingest
        scoreboard games for that date.
        """
        league = self._get_league(league_id)
        sport_id = int(league["sport"])
        api_keyword, api_group_ids, base_url = self._get_sport_api_config(sport_id)

        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season["sportSeasonId"])

        client = ESPNClient(self.espn_base_url, api_keyword)
        datestr = target_date.strftime("%Y%m%d")

        logger.info(
            "Ingesting scoreboard for league %s (sport=%s, sportSeasonId=%s) date=%s",
            league_id, sport_id, sport_season_id, datestr
        )

        events_seen = 0

        for group_id in api_group_ids:
            scoreboard_json = client.fetch_scoreboard_for_date(datestr, group_id)

            for event in client.iter_team_events(scoreboard_json):
                events_seen += 1
                game = client.extract_game_from_event(event)
                if not game:
                    continue

                self._insert_or_update_game(sport_id, sport_season_id, game)

        return {
            "leagueId": league_id,
            "sportId": sport_id,
            "sportSeasonId": sport_season_id,
            "date": target_date.isoformat(),
            "eventsSeen": events_seen
        }

    def get_member_games_for_week(
        self,
        league_id: int,
        member_id: int,
        week_number: int,
    ) -> list[dict]:
        """
        Return all games that count for this member in this week, with memberPointDiff
        already computed (everyone-vs-everyone, single-owner perspective).
        """
        sql = text("""
            WITH target_week AS (
            SELECT
                w."startDate",
                w."endDate",
                l."sport"        AS "sportId",
                l."seasonYear"   AS "seasonYear",
                ss.id            AS "sportSeasonId"
            FROM "Week" w
            JOIN "League" l
                ON l.id = w."leagueId"
            JOIN "SportSeason" ss
                ON ss."sportId"    = l."sport"
            AND ss."seasonYear" = l."seasonYear"
            WHERE w."leagueId"   = :leagueId
                AND w."weekNumber" = :weekNumber
            LIMIT 1
            ),
            member_teams AS (
            SELECT lts."sportTeamId"
            FROM "LeagueTeamSlot" lts
            WHERE lts."leagueId"   = :leagueId
                AND lts."memberId"   = :memberId
                AND lts."acquiredWeek" <= :weekNumber
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            )
            SELECT
            gr.id,
            gr."externalGameId",
            gr.date,
            gr.broadcast,
            gr."homeTeamId",
            gr."awayTeamId",
            gr."homeTeamName",
            gr."awayTeamName",
            gr."homeScore",
            gr."awayScore",
            (gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)) AS "ownsHome",
            (gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)) AS "ownsAway",
            CASE
                WHEN gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                    AND gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                THEN 0
                WHEN gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                THEN gr."homeScore" - gr."awayScore"
                WHEN gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                THEN gr."awayScore" - gr."homeScore"
                ELSE 0
            END AS "memberPointDiff"
            FROM "GameResult" gr,
                target_week tw
            WHERE gr.sport           = tw."sportId"
            AND gr."sportSeasonId" = tw."sportSeasonId"
            AND gr.date BETWEEN tw."startDate" AND tw."endDate"
            AND (
                gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                OR
                gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)
            )
            ORDER BY gr.date, gr."externalGameId";
        """)

        with self.db.begin() as conn:
            rows = conn.execute(
                sql,
                {
                    "leagueId": league_id,
                    "memberId": member_id,
                    "weekNumber": week_number,
                },
            ).fetchall()

        return [dict(r._mapping) for r in rows]
    
    def get_head_to_head_games(
        self,
        league_id: int,
        member_a_id: int,
        member_b_id: int,
        week_number: int,
    ) -> list[dict]:
        """
        All games in this week where a team owned by member A played
        a team owned by member B (in either home/away direction).
        """
        sql = text("""
            WITH target_week AS (
            SELECT
                w."startDate",
                w."endDate",
                l."sport"        AS "sportId",
                l."seasonYear"   AS "seasonYear",
                ss.id            AS "sportSeasonId"
            FROM "Week" w
            JOIN "League" l
                ON l.id = w."leagueId"
            JOIN "SportSeason" ss
                ON ss."sportId"    = l."sport"
            AND ss."seasonYear" = l."seasonYear"
            WHERE w."leagueId"   = :leagueId
                AND w."weekNumber" = :weekNumber
            LIMIT 1
            ),
            a_teams AS (
            SELECT lts."sportTeamId"
            FROM "LeagueTeamSlot" lts
            WHERE lts."leagueId"   = :leagueId
                AND lts."memberId"   = :memberA
                AND lts."acquiredWeek" <= :weekNumber
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            ),
            b_teams AS (
            SELECT lts."sportTeamId"
            FROM "LeagueTeamSlot" lts
            WHERE lts."leagueId"   = :leagueId
                AND lts."memberId"   = :memberB
                AND lts."acquiredWeek" <= :weekNumber
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            )
            SELECT
            gr.id,
            gr."externalGameId",
            gr.date,
            gr."homeTeamId",
            gr."awayTeamId",
            gr."homeTeamName",
            gr."awayTeamName",
            gr."homeScore",
            gr."awayScore",
            (gr."homeTeamId" IN (SELECT "sportTeamId" FROM a_teams)) AS "homeOwnedByA",
            (gr."awayTeamId" IN (SELECT "sportTeamId" FROM a_teams)) AS "awayOwnedByA",
            (gr."homeTeamId" IN (SELECT "sportTeamId" FROM b_teams)) AS "homeOwnedByB",
            (gr."awayTeamId" IN (SELECT "sportTeamId" FROM b_teams)) AS "awayOwnedByB"
            FROM "GameResult" gr,
                target_week tw
            WHERE gr.sport           = tw."sportId"
            AND gr."sportSeasonId" = tw."sportSeasonId"
            AND gr.date BETWEEN tw."startDate" AND tw."endDate"
            AND (
                (gr."homeTeamId" IN (SELECT "sportTeamId" FROM a_teams)
                AND gr."awayTeamId" IN (SELECT "sportTeamId" FROM b_teams))
                OR
                (gr."homeTeamId" IN (SELECT "sportTeamId" FROM b_teams)
                AND gr."awayTeamId" IN (SELECT "sportTeamId" FROM a_teams))
            )
            ORDER BY gr.date, gr."externalGameId";
        """)

        with self.db.begin() as conn:
            rows = conn.execute(
                sql,
                {
                    "leagueId": league_id,
                    "weekNumber": week_number,
                    "memberA": member_a_id,
                    "memberB": member_b_id,
                },
            ).fetchall()

        return [dict(r._mapping) for r in rows]

    def _lookup_season_phase_id_for_game(
        self,
        sport_season_id: int,
        event_dt: dt.datetime,
        ) -> Optional[int]:
        """
        Given a sportSeason + game datetime, find the matching SeasonPhase (if any).
        Assumes SeasonPhase has a date range for the phase.
        """

        sql = text("""
            SELECT sp.id
            FROM "SeasonPhase" sp
            WHERE sp."sportSeasonId" = :sportSeasonId
            AND :eventDate >= sp."startDate"
            AND :eventDate <  sp."endDate"
            ORDER BY sp."priority" ASC, sp."startDate" DESC, sp.id DESC
            LIMIT 1;
        """)

        with self.db.begin() as conn:
            row = conn.execute(
                sql,
                {
                    "sportSeasonId": sport_season_id,
                    "eventDate": event_dt,
                },
            ).fetchone()

        return int(row[0]) if row else None
    
    def get_week_for_league(
        self,
        league_id: int,
        week_number: int,
    ) -> dict | None:
        """
        Return the Week row for a given league + weekNumber, or None if missing.
        """
        sql = text("""
            SELECT
                id,
                "createdAt",
                "leagueId",
                "weekNumber",
                "startDate",
                "endDate",
                "isLocked",
                "scoringComplete"
            FROM "Week"
            WHERE "leagueId"   = :leagueId
              AND "weekNumber" = :weekNumber
            LIMIT 1
        """)

        with self.db.begin() as conn:
            row = conn.execute(
                sql,
                {
                    "leagueId": league_id,
                    "weekNumber": week_number,
                },
            ).fetchone()

        return dict(row._mapping) if row else None

    def get_owned_teams_for_member(
        self,
        league_id: int,
        member_id: int,
        week_number: int,
    ) -> list[dict]:
        """
        Return all teams this member owns in this league for the given week.
        Uses the same acquisition / drop logic as get_member_games_for_week.
        """
        sql = text("""
            WITH member_teams AS (
                SELECT lts."sportTeamId"
                FROM "LeagueTeamSlot" lts
                WHERE lts."leagueId"     = :leagueId
                AND lts."memberId"     = :memberId
                AND lts."acquiredWeek" <= :weekNumber
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            )
            SELECT
                st.id              AS "teamId",
                st."displayName"   AS "teamName",
                c.name             AS "conferenceName"
            FROM member_teams mt
            JOIN "SportTeam" st
            ON st.id = mt."sportTeamId"
            LEFT JOIN "ConferenceMembership" cm
            ON cm."sportTeamId" = st.id
            LEFT JOIN "SportConference" sc
            ON sc.id = cm."sportConferenceId"
            LEFT JOIN "Conference" c
            ON c.id = sc."conferenceId"
            ORDER BY st."displayName";
        """)

        with self.db.begin() as conn:
            rows = conn.execute(
                sql,
                {
                    "leagueId": league_id,
                    "memberId": member_id,
                    "weekNumber": week_number,
                },
            ).fetchall()

        return [dict(r._mapping) for r in rows]

    def _get_week_window(self, league_id: int, week_number: int) -> Tuple[str, str]:
        """
        Returns (startDate, endDate) for the league week.
        """
        sql = text("""
            SELECT "startDate", "endDate"
            FROM "Week"
            WHERE "leagueId" = :leagueId
              AND "weekNumber" = :weekNumber
            LIMIT 1
        """)
        with self.db.begin() as conn:
            row = conn.execute(sql, {"leagueId": league_id, "weekNumber": week_number}).fetchone()

        if not row:
            raise ValueError(f"Week not found for leagueId={league_id}, weekNumber={week_number}")

        m = row._mapping
        return (m["startDate"], m["endDate"])

    def get_conference_games_by_week(
        self,
        league_id: int,
        week_number: int,
        season_year: int,
        sport_conference_id: int,
    ) -> List[Dict[str, Any]]:
        week_start, week_end = self._get_week_window(league_id, week_number)

        sql = text("""
            WITH sc AS (
                SELECT id, "sportId"
                FROM "SportConference"
                WHERE id = :sportConferenceId
                LIMIT 1
            ),
            ss AS (
                SELECT s.id AS "sportSeasonId"
                FROM "SportSeason" s
                JOIN sc ON sc."sportId" = s."sportId"
                WHERE s."seasonYear" = :seasonYear
                LIMIT 1
            ),
            conf_teams AS (
                SELECT cm."sportTeamId"
                FROM "ConferenceMembership" cm
                WHERE cm."sportConferenceId" = :sportConferenceId
                  AND (cm."seasonYear" IS NULL OR cm."seasonYear" = :seasonYear)
            )
            SELECT
                gr.id,
                gr."externalGameId",
                gr.date,
                gr.sport,
                gr."sportSeasonId",
                gr."seasonPhaseId",
                gr."roundOrder",
                gr."homeTeamId",
                gr."awayTeamId",
                gr."broadcast",
                gr."homeTeamName",
                gr."awayTeamName",
                gr."homeScore",
                gr."awayScore",
                (gr."homeTeamId" IN (SELECT "sportTeamId" FROM conf_teams)) AS "homeInConference",
                (gr."awayTeamId" IN (SELECT "sportTeamId" FROM conf_teams)) AS "awayInConference"
            FROM "GameResult" gr
            JOIN ss ON ss."sportSeasonId" = gr."sportSeasonId"
            WHERE (
                gr."homeTeamId" IN (SELECT "sportTeamId" FROM conf_teams)
                OR gr."awayTeamId" IN (SELECT "sportTeamId" FROM conf_teams)
            )
              AND gr.date >= :weekStart
              AND gr.date <= :weekEnd
            ORDER BY gr.date, gr."externalGameId";
        """)

        with self.db.begin() as conn:
            rows = conn.execute(sql, {
                "sportConferenceId": sport_conference_id,
                "seasonYear": season_year,
                "weekStart": week_start,
                "weekEnd": week_end,
            }).fetchall()

        return [dict(r._mapping) for r in rows]

    def get_team_games_by_season(
        self,
        sport_team_id: int,
        season_year: int,
    ) -> List[Dict[str, Any]]:
        """
        All games for a given SportTeam across the entire SportSeason for seasonYear.
        """
        sql = text("""
            WITH st AS (
                SELECT id, "sportId"
                FROM "SportTeam"
                WHERE id = :sportTeamId
                LIMIT 1
            ),
            ss AS (
                SELECT s.id AS "sportSeasonId"
                FROM "SportSeason" s
                JOIN st ON st."sportId" = s."sportId"
                WHERE s."seasonYear" = :seasonYear
                LIMIT 1
            )
            SELECT
                gr.id,
                gr."externalGameId",
                gr.date,
                gr.sport,
                gr."broadcast",
                gr."sportSeasonId",
                gr."seasonPhaseId",
                gr."roundOrder",
                gr."homeTeamId",
                gr."awayTeamId",
                gr."homeTeamName",
                gr."awayTeamName",
                gr."homeScore",
                gr."awayScore",
                (gr."homeTeamId" = :sportTeamId) AS "isHome",
                CASE
                    WHEN gr."homeTeamId" = :sportTeamId THEN gr."awayTeamId"
                    ELSE gr."homeTeamId"
                END AS "opponentTeamId",
                CASE
                    WHEN gr."homeTeamId" = :sportTeamId THEN gr."awayTeamName"
                    ELSE gr."homeTeamName"
                END AS "opponentTeamName"
            FROM "GameResult" gr
            JOIN ss ON ss."sportSeasonId" = gr."sportSeasonId"
            WHERE (gr."homeTeamId" = :sportTeamId OR gr."awayTeamId" = :sportTeamId)
            ORDER BY gr.date, gr."externalGameId";
        """)

        with self.db.begin() as conn:
            rows = conn.execute(
                sql,
                {"sportTeamId": sport_team_id, "seasonYear": season_year},
            ).fetchall()

        return [dict(r._mapping) for r in rows]
    
    def upsert_sport_season(
        self,
        conn,
        sport_id: int,
        season_year: int,
        regular_start: dt.datetime,
        regular_end: dt.datetime,
        playoff_start: Optional[dt.datetime],
        playoff_end: Optional[dt.datetime],
    ) -> int:
        row = conn.execute(
            text("""
                INSERT INTO "SportSeason"
                    ("sportId","seasonYear","regularSeasonStart","regularSeasonEnd","playoffStart","playoffEnd")
                VALUES
                    (:sportId,:year,:rs,:re,:ps,:pe)
                ON CONFLICT ("sportId","seasonYear")
                DO UPDATE SET
                    "regularSeasonStart" = EXCLUDED."regularSeasonStart",
                    "regularSeasonEnd"   = EXCLUDED."regularSeasonEnd",
                    "playoffStart"       = EXCLUDED."playoffStart",
                    "playoffEnd"         = EXCLUDED."playoffEnd"
                RETURNING id
            """),
            {
                "sportId": sport_id,
                "year": season_year,
                "rs": regular_start,
                "re": regular_end,
                "ps": playoff_start,
                "pe": playoff_end,
            },
        ).fetchone()

        return int(row[0])
