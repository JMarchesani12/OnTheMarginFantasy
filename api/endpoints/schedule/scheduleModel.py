import datetime as dt
import json
import re
from typing import Any, Dict, List, Optional

from rules.leagueRules import resolve_rules, adjust_margin
from rules.tournamentRules import score_margin, select_phase, final_period
from sqlalchemy import text
from sqlalchemy.engine import Engine
from .calendar_service import ScheduleCalendarService, WEEKDAY_NUMBERS, SPORT_WEEK_START_WEEKDAYS
from zoneinfo import ZoneInfo

from endpoints.schedule.helpers.espn.espnClient import ESPNClient
from endpoints.schedule.helpers.bootstrapCheckpoint import (
    BootstrapCheckpoint, default_checkpoint_path, fingerprint,
)
from endpoints.schedule.helpers.weekHelper import (
    compute_weeks_from_start,
    partition_initial_partial_week,
)


# Basketball and future sports default to Monday. College football uses Tuesday.


class ScheduleModel(ScheduleCalendarService):
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

    @staticmethod
    def _apply_tier_adjustment(
        raw_point_diff: int,
        owned_team_tier: Optional[int],
        opponent_team_tier: Optional[int],
        sport_id: Optional[int] = None,
    ) -> int:
        return adjust_margin(raw_point_diff, owned_team_tier, opponent_team_tier,
                             resolve_rules(sport_id, {}))['adjustedMargin']

    # -------------------------------------------------------------------------
    # Basic lookups
    # -------------------------------------------------------------------------


    


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
            game=game, home_team_id=home_team_id, away_team_id=away_team_id,
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
                raise RuntimeError(f"Scoreboard fetch failed for sport={sport_id}, date={datestr}, group={group_id}") from e

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
        checkpoint_path=None,
    ) -> Dict[str, Any]:
        """
        Ingest pending dates, checkpointing each successful day. Reruns resume;
        force discards checkpoints and refreshes the full date range.
        """

        with self.db.begin() as conn:
            ss = conn.execute(
                text("""
                    SELECT
                        id,
                        "sportId",
                        COALESCE("scheduleBootstrapped", false) AS "scheduleBootstrapped",
                        "seasonStart"::date AS "seasonStart",
                        "seasonEnd"::date AS "seasonEnd"
                    FROM "SportSeason"
                    WHERE id = :id
                """),
                {"id": sport_season_id},
            ).mappings().first()

        if not ss:
            raise ValueError(f"SportSeason {sport_season_id} not found")

        start_date = ss["seasonStart"]
        end_date = ss["seasonEnd"]

        if not start_date or not end_date:
            raise ValueError("SportSeason missing seasonStart/seasonEnd")

        if end_date < start_date:
            raise ValueError(f"Invalid season window: {start_date} -> {end_date}")

        if max_days is not None and (isinstance(max_days, bool) or max_days <= 0):
            raise ValueError("max_days must be a positive integer")
        api_keyword, api_groups, _ = self._get_sport_api_config(int(ss["sportId"]))
        identity = fingerprint({
            "database": str(self.db.url), "season": sport_season_id,
            "sport": ss["sportId"], "start": start_date, "end": end_date,
            "source": self.espn_base_url, "apiKeyword": api_keyword,
            "apiGroups": sorted(set(api_groups)),
            "phases": sorted([
                {key: phase.get(key) for key in
                 ('id', 'type', 'tournamentId', 'sportConferenceId', 'startDate', 'endDate', 'rules')}
                for phase in self._get_season_phases(sport_season_id)
            ], key=lambda phase: phase['id']),
        })
        checkpoint = BootstrapCheckpoint(
            checkpoint_path or default_checkpoint_path(self.db.url, sport_season_id), identity, reset=force)
        if ss["scheduleBootstrapped"] and not force and not (checkpoint.resuming and not checkpoint.complete):
            return {
                "sportId": int(ss["sportId"]), "sportSeasonId": sport_season_id,
                "skipped": True, "reason": "already scheduleBootstrapped (use force=True to re-run)",
            }
        all_dates = [start_date + dt.timedelta(days=n) for n in range((end_date - start_date).days + 1)]
        pending = [d for d in all_dates if d not in checkpoint.completed]
        days_skipped = len(all_dates) - len(pending)
        if max_days is not None:
            pending = pending[:max_days]
        checkpoint.complete = False
        checkpoint.save()
        with self.db.begin() as conn:
            conn.execute(text('''
                UPDATE "SportSeason" SET "scheduleBootstrapped"=false, "scheduleBootstrappedAt"=NULL
                WHERE id=:id
            '''), {"id": sport_season_id})
        print(f"[bootstrap] Checkpoint: {checkpoint.path}")
        print(f"[bootstrap] Skipping {days_skipped} completed dates; processing {len(pending)} dates")
        days_processed = failed_days = events_seen_total = games_upserted_total = 0
        for d in pending:
            try:
                summary = self.ingest_scoreboard_for_date_for_sport_season(sport_season_id, d)
            except Exception as e:
                failed_days += 1
                print(f"[bootstrap-by-date] ERROR sportSeasonId={sport_season_id} date={d}: {e}")
            else:
                events_seen_total += int(summary.get("eventsSeen", 0))
                games_upserted_total += int(summary.get("gamesUpserted", 0))
                checkpoint.completed.add(d)
                checkpoint.save()
                print(f"[bootstrap] Completed {d}: {summary.get('gamesUpserted', 0)} games")
            days_processed += 1
        complete = all(d in checkpoint.completed for d in all_dates)
        checkpoint.complete = complete
        checkpoint.save()
        with self.db.begin() as conn:
            conn.execute(
                text("""
                    UPDATE "SportSeason"
                    SET "scheduleBootstrapped" = :complete,
                        "scheduleBootstrappedAt" = CASE WHEN :complete THEN now() ELSE NULL END
                    WHERE id = :id
                """),
                {"id": sport_season_id, "complete": complete},
            )

        return {
            "sportId": int(ss["sportId"]),
            "sportSeasonId": sport_season_id,
            "startDate": str(start_date),
            "endDate": str(end_date),
            "daysProcessed": days_processed,
            "daysSkipped": days_skipped,
            "checkpointPath": str(checkpoint.path),
            "failedDays": failed_days,
            "complete": complete,
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
        resolved_rules: Optional[dict] = None,
    ) -> list[dict]:
        """
        Return all games that count for this member in this week, with memberPointDiff
        already computed (everyone-vs-everyone, single-owner perspective).
        """
        if resolved_rules is None:
            league = self._get_league(league_id)
            resolved_rules = resolve_rules(league['sport'], league.get('settings'))
        sql = text("""
            WITH target_week AS (
            SELECT
                COALESCE(
                    w."startDate",
                    w."endDate" + interval '1 microsecond' - interval '7 days'
                ) AS "startDate",
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
            ),
            max_tier AS (
            SELECT COALESCE(MAX(st.tier), 0) AS "maxTier"
            FROM "SportTeam" st,
                target_week tw
            WHERE st."sportId" = tw."sportId"
            )
            SELECT
            gr.id,
            gr."externalGameId",
            gr.date,
            tw."sportId",
            gr.broadcast,
            COALESCE(sp.rules, '{}'::jsonb) AS "phaseRules",
            gr."homeTeamId",
            gr."awayTeamId",
            gr."homeTeamName",
            gr."awayTeamName",
            gr."homeScore",
            gr."awayScore",
            (gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)) AS "ownsHome",
            (gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)) AS "ownsAway",
            COALESCE(home_st.tier, mt."maxTier" + 1) AS "homeTeamTier",
            COALESCE(away_st.tier, mt."maxTier" + 1) AS "awayTeamTier",
            (home_st.tier IS NULL) AS "homeTeamUnranked",
            (away_st.tier IS NULL) AS "awayTeamUnranked",
            CASE
                WHEN gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                    AND gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                THEN 0
                WHEN gr."homeTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                THEN gr."homeScore" - gr."awayScore"
                WHEN gr."awayTeamId" IN (SELECT "sportTeamId" FROM member_teams)
                THEN gr."awayScore" - gr."homeScore"
                ELSE 0
            END AS "rawMemberPointDiff"
            FROM "GameResult" gr
            LEFT JOIN "SeasonPhase" sp ON sp.id=gr."seasonPhaseId"
            CROSS JOIN target_week tw
            CROSS JOIN max_tier mt
            LEFT JOIN "SportTeam" home_st
                ON home_st.id = gr."homeTeamId"
            LEFT JOIN "SportTeam" away_st
                ON away_st.id = gr."awayTeamId"
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

        games = []
        rules = resolved_rules
        for row in rows:
            game = dict(row._mapping)
            owns_home, owns_away = game['ownsHome'], game['ownsAway']
            owned_tier = game.get('homeTeamTier') if owns_home else game.get('awayTeamTier')
            opponent_tier = game.get('awayTeamTier') if owns_home else game.get('homeTeamTier')
            adjustment = adjust_margin(game['rawMemberPointDiff'], owned_tier, opponent_tier,
                                       rules, double_owned=owns_home and owns_away)
            if not owns_home and not owns_away:
                adjustment = adjust_margin(0, None, None, rules)
            game['memberPointDiff'] = score_margin(adjustment['adjustedMargin'], game.get('phaseRules') or {})
            game['tournamentAdjustment'] = {
                'positiveOnly': (game.get('phaseRules') or {}).get('positiveOnly', False),
                'multiplier': (game.get('phaseRules') or {}).get('marginMultiplier', 1),
                'scoringMargin': game['memberPointDiff'],
            }
            game['tierAdjustment'] = adjustment
            games.append(game)

        return games
    
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
        game=None, home_team_id=None, away_team_id=None,
        ) -> Optional[int]:
        """
        Given a sportSeason + game datetime, find the matching SeasonPhase (if any).
        Assumes SeasonPhase has a date range for the phase.
        """

        phases = self._get_season_phases(sport_season_id)
        if any(p.get('rules') for p in phases):
            conference_ids = set()
            if home_team_id is not None and away_team_id is not None:
                with self.db.begin() as conn:
                    rows = conn.execute(text('''
                        SELECT DISTINCT a."sportConferenceId"
                        FROM "ConferenceMembership" a
                        JOIN "ConferenceMembership" b
                          ON b."sportConferenceId"=a."sportConferenceId" AND b."sportId"=a."sportId"
                        JOIN "SportSeason" ss ON ss.id=:season AND ss."sportId"=a."sportId"
                        WHERE a."sportTeamId"=:home AND b."sportTeamId"=:away
                          AND (a."seasonYear"=ss."seasonYear" OR (a."seasonYear" IS NULL AND NOT EXISTS (
                              SELECT 1 FROM "ConferenceMembership" x WHERE x."sportTeamId"=a."sportTeamId"
                              AND x."sportId"=a."sportId" AND x."seasonYear"=ss."seasonYear")))
                          AND (b."seasonYear"=ss."seasonYear" OR (b."seasonYear" IS NULL AND NOT EXISTS (
                              SELECT 1 FROM "ConferenceMembership" x WHERE x."sportTeamId"=b."sportTeamId"
                              AND x."sportId"=b."sportId" AND x."seasonYear"=ss."seasonYear")))
                    '''), {"season": sport_season_id, "home": home_team_id, "away": away_team_id}).fetchall()
                conference_ids = {int(row[0]) for row in rows}
            dated = [p for p in phases if p['startDate'] is not None and p['endDate'] is not None]
            return select_phase(dated, game or {}, event_dt, conference_ids)

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
                w.id,
                w."createdAt",
                w."leagueId",
                w."weekNumber",
                COALESCE(
                    w."startDate",
                    w."endDate" + interval '1 microsecond' - interval '7 days'
                ) AS "startDate",
                w."endDate",
                w."isLocked",
                w."scoringComplete"
            FROM "Week" w
            JOIN "League" l
              ON l.id = w."leagueId"
            JOIN "SportSeason" ss
              ON ss."sportId" = l.sport
             AND ss."seasonYear" = l."seasonYear"
            WHERE w."leagueId"   = :leagueId
              AND w."weekNumber" = :weekNumber
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
                COALESCE(st.tier, (
                  SELECT COALESCE(MAX(tier_team.tier), 0) + 1
                  FROM "SportTeam" tier_team
                  WHERE tier_team."sportId" = st."sportId"
                )) AS "tier",
                sc.id              AS "sportConferenceId",
                c.name             AS "conferenceName"
            FROM member_teams mt
            JOIN "SportTeam" st
            ON st.id = mt."sportTeamId"
            LEFT JOIN "ConferenceMembership" cm
            ON cm."sportTeamId" = st.id
            AND cm."sportId" = st."sportId"
            LEFT JOIN "SportConference" sc
            ON sc.id = cm."sportConferenceId"
            AND sc."sportId" = st."sportId"
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
            SELECT
                COALESCE(
                    w."startDate",
                    w."endDate" + interval '1 microsecond' - interval '7 days'
                ) AS "startDate",
                w."endDate"
            FROM "Week" w
            JOIN "League" l
              ON l.id = w."leagueId"
            JOIN "SportSeason" ss
              ON ss."sportId" = l.sport
             AND ss."seasonYear" = l."seasonYear"
            WHERE w."leagueId" = :leagueId
              AND w."weekNumber" = :weekNumber
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
                SELECT id, "sportId", "conferenceId"
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
                SELECT st.id AS "sportTeamId"
                FROM "ConferenceMembership" cm
                JOIN sc
                  ON sc."sportId" = cm."sportId"
                 AND sc.id = cm."sportConferenceId"
                JOIN "SportTeam" st
                  ON st.id = cm."sportTeamId"
                 AND st."sportId" = sc."sportId"
                WHERE (cm."seasonYear" IS NULL OR cm."seasonYear" = :seasonYear)
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
                home_lm.id AS "homeOwnerMemberId",
                home_lm."teamName" AS "homeOwnerTeamName",
                home_u."displayName" AS "homeOwnerDisplayName",
                away_lm.id AS "awayOwnerMemberId",
                away_lm."teamName" AS "awayOwnerTeamName",
                away_u."displayName" AS "awayOwnerDisplayName",
                (gr."homeTeamId" IN (SELECT "sportTeamId" FROM conf_teams)) AS "homeInConference",
                (gr."awayTeamId" IN (SELECT "sportTeamId" FROM conf_teams)) AS "awayInConference"
            FROM "GameResult" gr
            JOIN ss ON ss."sportSeasonId" = gr."sportSeasonId"
            LEFT JOIN "LeagueTeamSlot" home_lts
              ON home_lts."leagueId" = :leagueId
             AND home_lts."sportTeamId" = gr."homeTeamId"
             AND home_lts."acquiredWeek" <= :weekNumber
             AND (home_lts."droppedWeek" IS NULL OR home_lts."droppedWeek" > :weekNumber)
            LEFT JOIN "LeagueMember" home_lm
              ON home_lm.id = home_lts."memberId"
            LEFT JOIN "User" home_u
              ON home_u.id = home_lm."userId"
            LEFT JOIN "LeagueTeamSlot" away_lts
              ON away_lts."leagueId" = :leagueId
             AND away_lts."sportTeamId" = gr."awayTeamId"
             AND away_lts."acquiredWeek" <= :weekNumber
             AND (away_lts."droppedWeek" IS NULL OR away_lts."droppedWeek" > :weekNumber)
            LEFT JOIN "LeagueMember" away_lm
              ON away_lm.id = away_lts."memberId"
            LEFT JOIN "User" away_u
              ON away_u.id = away_lm."userId"
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
                "leagueId": league_id,
                "weekNumber": week_number,
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
        league_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        All games for a given SportTeam across the entire SportSeason for seasonYear.
        """
        league_context_sql = text("""
            SELECT
                COALESCE(current_week."weekNumber", latest_week."weekNumber", 999) AS "weekNumber"
            FROM "League" l
            LEFT JOIN LATERAL (
                SELECT w."weekNumber"
                FROM "Week" w
                WHERE w."leagueId" = l.id
                  AND now() >= COALESCE(
                    w."startDate",
                    w."endDate" + interval '1 microsecond' - interval '7 days'
                  )
                  AND now() <= w."endDate"
                ORDER BY w."weekNumber" DESC
                LIMIT 1
            ) current_week ON true
            LEFT JOIN LATERAL (
                SELECT w."weekNumber"
                FROM "Week" w
                WHERE w."leagueId" = l.id
                ORDER BY w."weekNumber" DESC
                LIMIT 1
            ) latest_week ON true
            WHERE l.id = :leagueId
            LIMIT 1
        """)
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
                END AS "opponentTeamName",
                owner_lm.id AS "ownerMemberId",
                owner_lm."teamName" AS "ownerTeamName",
                owner_u."displayName" AS "ownerDisplayName"
            FROM "GameResult" gr
            JOIN ss ON ss."sportSeasonId" = gr."sportSeasonId"
            LEFT JOIN "LeagueTeamSlot" owner_lts
              ON :leagueId IS NOT NULL
             AND owner_lts."leagueId" = :leagueId
             AND owner_lts."sportTeamId" = :sportTeamId
             AND owner_lts."acquiredWeek" <= :weekNumber
             AND (owner_lts."droppedWeek" IS NULL OR owner_lts."droppedWeek" > :weekNumber)
            LEFT JOIN "LeagueMember" owner_lm
              ON owner_lm.id = owner_lts."memberId"
            LEFT JOIN "User" owner_u
              ON owner_u.id = owner_lm."userId"
            WHERE (gr."homeTeamId" = :sportTeamId OR gr."awayTeamId" = :sportTeamId)
            ORDER BY gr.date, gr."externalGameId";
        """)

        with self.db.begin() as conn:
            week_number = 999
            if league_id is not None:
                league_context = conn.execute(
                    league_context_sql,
                    {"leagueId": league_id},
                ).fetchone()
                if league_context:
                    week_number = int(league_context._mapping["weekNumber"] or 999)

            rows = conn.execute(
                sql,
                {
                    "sportTeamId": sport_team_id,
                    "seasonYear": season_year,
                    "leagueId": league_id,
                    "weekNumber": week_number,
                },
            ).fetchall()

        return [dict(r._mapping) for r in rows]

    @staticmethod
    def _normalize_team_search_text(value: str) -> str:
        abbreviations = {
            "st": "state",
            "univ": "university",
        }
        cleaned = re.sub(
            r"[^a-z0-9]+",
            " ",
            (value or "").lower().replace("&", " and "),
        )
        tokens = [abbreviations.get(token, token) for token in cleaned.split()]
        return " ".join(tokens)

    @classmethod
    def _team_search_rank(cls, row: Dict[str, Any], query: str) -> int:
        normalized_query = cls._normalize_team_search_text(query)
        if not normalized_query:
            return 0

        normalized_candidate = cls._normalize_team_search_text(row.get("teamName") or "")
        if normalized_candidate == normalized_query:
            return 100
        if normalized_candidate.startswith(normalized_query):
            return 90
        if normalized_query in normalized_candidate:
            return 75

        candidate_tokens = normalized_candidate.split()
        query_tokens = normalized_query.split()
        if query_tokens and all(
            any(candidate_token.startswith(query_token) for candidate_token in candidate_tokens)
            for query_token in query_tokens
        ):
            return 50
        return 0

    def search_teams_for_league(
        self,
        league_id: int,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        limit = max(1, min(int(limit or 20), 50))
        normalized_query = self._normalize_team_search_text(query)
        if len(normalized_query) < 2:
            return []

        league_sql = text("""
            SELECT
                l.sport,
                l."seasonYear",
                COALESCE(current_week."weekNumber", latest_week."weekNumber", 999) AS "weekNumber"
            FROM "League" l
            LEFT JOIN LATERAL (
                SELECT w."weekNumber"
                FROM "Week" w
                WHERE w."leagueId" = l.id
                  AND now() >= COALESCE(
                    w."startDate",
                    w."endDate" + interval '1 microsecond' - interval '7 days'
                  )
                  AND now() <= w."endDate"
                ORDER BY w."weekNumber" DESC
                LIMIT 1
            ) current_week ON true
            LEFT JOIN LATERAL (
                SELECT w."weekNumber"
                FROM "Week" w
                WHERE w."leagueId" = l.id
                ORDER BY w."weekNumber" DESC
                LIMIT 1
            ) latest_week ON true
            WHERE l.id = :leagueId
            LIMIT 1
        """)

        team_sql = text("""
            SELECT
                st.id AS "teamId",
                st."displayName" AS "teamName",
                c.name AS "conferenceName",
                lm.id AS "ownerMemberId",
                lm."teamName" AS "ownerTeamName",
                u."displayName" AS "ownerDisplayName"
            FROM "SportTeam" st
            LEFT JOIN "ConferenceMembership" cm
              ON cm."sportTeamId" = st.id
             AND cm."sportId" = st."sportId"
             AND (cm."seasonYear" IS NULL OR cm."seasonYear" = :seasonYear)
            LEFT JOIN "SportConference" sc
              ON sc.id = cm."sportConferenceId"
             AND sc."sportId" = st."sportId"
            LEFT JOIN "Conference" c
              ON c.id = sc."conferenceId"
            LEFT JOIN "LeagueTeamSlot" lts
              ON lts."leagueId" = :leagueId
             AND lts."sportTeamId" = st.id
             AND lts."acquiredWeek" <= :weekNumber
             AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            LEFT JOIN "LeagueMember" lm
              ON lm.id = lts."memberId"
            LEFT JOIN "User" u
              ON u.id = lm."userId"
            WHERE st."sportId" = :sport
            ORDER BY st."displayName"
        """)

        with self.db.begin() as conn:
            league_row = conn.execute(league_sql, {"leagueId": league_id}).fetchone()
            if not league_row:
                raise ValueError(f"League not found: {league_id}")

            league = dict(league_row._mapping)
            rows = conn.execute(
                team_sql,
                {
                    "leagueId": league_id,
                    "sport": league["sport"],
                    "seasonYear": league["seasonYear"],
                    "weekNumber": int(league["weekNumber"] or 999),
                },
            ).fetchall()

        ranked = []
        for row in rows:
            item = dict(row._mapping)
            rank = self._team_search_rank(item, normalized_query)
            if rank > 0:
                ranked.append((rank, item["teamName"], item))

        ranked.sort(key=lambda value: (-value[0], value[1]))
        return [item for _, _, item in ranked[:limit]]
    
    def upsert_sport_season(
        self,
        conn,
        sport_id: int,
        season_year: int,
        season_start: dt.date,
        season_end: dt.date,
    ) -> int:
        row = conn.execute(
            text("""
                INSERT INTO "SportSeason"
                    ("sportId", "seasonYear", "seasonStart", "seasonEnd")
                VALUES
                    (:sportId, :year, :seasonStart, :seasonEnd)
                ON CONFLICT ("sportId","seasonYear")
                DO UPDATE SET
                    "seasonStart" = EXCLUDED."seasonStart",
                    "seasonEnd" = EXCLUDED."seasonEnd"
                RETURNING id
            """),
            {
                "sportId": sport_id,
                "year": season_year,
                "seasonStart": season_start,
                "seasonEnd": season_end,
            },
        ).fetchone()

        return int(row[0])
