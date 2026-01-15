import datetime as dt
import json
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from endpoints.schedule.helpers.espn.espnClient import ESPNClient
from endpoints.schedule.helpers.weekHelper import compute_weeks_from_start

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

    def _get_sport_api_config(self, sport_id: int) -> tuple[str, List[int]]:
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
                    values (:leagueId, 0, null, :endDate, false, false)
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

        print(f"Inserted {len(created)} weeks for league {league_id} (starting_week_number={starting_week_number})")
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

        print(f"ensure_weeks_for_league created {len(created_all)} weeks for league {league_id}")
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
                print(f"Failed to fetch schedule for team {external_id}: {e}")
                continue

            for event in client.iter_scoreboard_events(schedule_json):
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
    
    def ingest_scoreboard_for_date_for_sport_season(
        self,
        sport_season_id: int,
        target_date: dt.date,
    ) -> Dict[str, Any]:
        """
        Ingest ESPN scoreboard for one date and upsert into GameResult.
        No leagues involved.
        """
        with self.db.begin() as conn:
            ss = conn.execute(
                text("""
                    SELECT id, "sportId"
                    FROM "SportSeason"
                    WHERE id = :id
                """),
                {"id": sport_season_id},
            ).mappings().first()

        if not ss:
            raise ValueError(f"SportSeason {sport_season_id} not found")

        sport_id = int(ss["sportId"])
        api_keyword, api_group_ids, base_url = self._get_sport_api_config(sport_id)

        client = ESPNClient(self.espn_base_url, api_keyword)
        datestr = target_date.strftime("%Y%m%d")

        events_seen = 0
        games_upserted = 0
        seen_external_game_ids = set()

        for group_id in api_group_ids:
            try:
                scoreboard_json = client.fetch_scoreboard_for_date(
                    datestr=datestr,
                    group_id=group_id,
                )
            except Exception as e:
                print(f"[scoreboard] ERROR sportId={sport_id} date={datestr} group={group_id}: {e}")
                continue

            for event in client.iter_scoreboard_events(scoreboard_json):
                game = client.extract_game_from_event(event)
                if not game:
                    continue

                external_game_id = game.get("externalGameId")
                if not external_game_id:
                    continue

                # Prevent duplicate upserts across groups
                if external_game_id in seen_external_game_ids:
                    continue

                seen_external_game_ids.add(external_game_id)
                events_seen += 1

                self._insert_or_update_game(
                    sport_id,
                    sport_season_id,
                    game,
                )
                games_upserted += 1

        return {
            "sportId": sport_id,
            "sportSeasonId": sport_season_id,
            "date": str(target_date),
            "eventsSeen": events_seen,
            "gamesUpserted": games_upserted,
        }
    
    def bootstrap_sport_season_schedule_by_scoreboard(
        self,
        sport_season_id: int,
        *,
        force: bool = False,
        max_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Bootstraps ALL regular-season games for a SportSeason by iterating
        from regularSeasonStart to regularSeasonEnd and ingesting the ESPN scoreboard each day.
        """

        with self.db.begin() as conn:
            ss = conn.execute(
                text("""
                    SELECT
                        id,
                        "sportId",
                        COALESCE("scheduleBootstrapped", false) AS "scheduleBootstrapped",
                        "regularSeasonStart"::date AS "regularSeasonStart",
                        "regularSeasonEnd"::date AS "regularSeasonEnd"
                    FROM "SportSeason"
                    WHERE id = :id
                """),
                {"id": sport_season_id},
            ).mappings().first()

        if not ss:
            raise ValueError(f"SportSeason {sport_season_id} not found")

        if ss["scheduleBootstrapped"] and not force:
            return {
                "sportId": int(ss["sportId"]),
                "sportSeasonId": sport_season_id,
                "skipped": True,
                "reason": "already scheduleBootstrapped (use force=True to re-run)",
            }

        start_date = ss["regularSeasonStart"]
        end_date = ss["regularSeasonEnd"]

        if not start_date or not end_date:
            raise ValueError("SportSeason missing regularSeasonStart/regularSeasonEnd")

        if end_date < start_date:
            raise ValueError(f"Invalid regular season window: {start_date} -> {end_date}")

        days_total = (end_date - start_date).days + 1
        if max_days is not None:
            days_total = min(days_total, max_days)

        days_processed = 0
        failed_days = 0
        events_seen_total = 0
        games_upserted_total = 0

        d = start_date
        for _ in range(days_total):
            try:
                summary = self.ingest_scoreboard_for_date_for_sport_season(sport_season_id, d)
                events_seen_total += int(summary.get("eventsSeen", 0))
                games_upserted_total += int(summary.get("gamesUpserted", 0))
            except Exception as e:
                failed_days += 1
                print(f"[bootstrap-by-date] ERROR sportSeasonId={sport_season_id} date={d}: {e}")
            finally:
                days_processed += 1
                d = d + dt.timedelta(days=1)

        with self.db.begin() as conn:
            conn.execute(
                text("""
                    UPDATE "SportSeason"
                    SET "scheduleBootstrapped" = true,
                        "scheduleBootstrappedAt" = now()
                    WHERE id = :id
                """),
                {"id": sport_season_id},
            )

        return {
            "sportId": int(ss["sportId"]),
            "sportSeasonId": sport_season_id,
            "startDate": str(start_date),
            "endDate": str(end_date),
            "daysProcessed": days_processed,
            "failedDays": failed_days,
            "eventsSeenTotal": events_seen_total,
            "gamesUpsertedTotal": games_upserted_total,
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

        print(f"Ingesting scoreboard for league {league_id} (sport={sport_id}, sportSeasonId={sport_season_id}) date={datestr}")

        events_seen = 0

        for group_id in api_group_ids:
            scoreboard_json = client.fetch_scoreboard_for_date(datestr, group_id)

            for event in client.iter_scoreboard_events(scoreboard_json):
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

    def _get_week_window(self, league_id: int, week_number: int) -> tuple[str, str]:
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
