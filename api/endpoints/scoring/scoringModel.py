import json
from typing import Any, Dict, List

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Engine

from endpoints.schedule.scheduleModel import ScheduleModel


class ScoringModel:
    """
    Computes weekly and season scores for leagues on top of global GameResult.

    - Uses:
        * League (sport, seasonYear, settings)
        * SportSeason (per-sport, per-year season metadata)
        * SeasonPhase (regular, conference tournaments, national tournaments, etc.)
        * Week (league-specific week ranges)
        * LeagueTeamSlot (ownership per week / season)
        * GameResult (global games with sportSeasonId, seasonPhaseId, roundOrder)
        * WeeklyTeamScore (per-league, per-week scoring)
        * BonusPointEvent (season bonuses)
    """

    PRIMARY_POSTSEASON_PHASE_TYPES = [
        "NationalTournament",   # legacy, CBB specific
        "PrimaryPlayoffs",      # generic, for other sports
    ]

    SEGMENT_POSTSEASON_PHASE_TYPES = [
        "ConferenceTournament", # legacy, CBB specific
        "SegmentPlayoffs",      # generic, for other sports
    ]

    BONUS_HANDLERS = {
        "playoffDepth": "_bonus_playoff_depth",
        "conferenceChampion": "_bonus_conference_champion",
        "conferenceBottom": "_bonus_conference_bottom",
    }

    def __init__(self, db: Engine, schedule_model: ScheduleModel):
        self.db = db
        self.schedule_model = schedule_model

    # ------------------------------------------------------------------
    # Basic helpers
    # ------------------------------------------------------------------

    def _get_league_settings(self, league_id: int) -> Dict[str, Any]:
        """
        Return League.settings JSON (may include bonuses, transactions, schedule).
        """
        sql = text("""
            SELECT settings
            FROM "League"
            WHERE id = :leagueId
        """)
        with self.db.begin() as conn:
            row = conn.execute(sql, {"leagueId": league_id}).fetchone()

        if not row:
            raise ValueError(f"League {league_id} not found")

        settings = row[0]
        if isinstance(settings, str):
            return json.loads(settings)
        return settings or {}

    def _get_week_by_number(self, league_id: int, week_number: int) -> Dict[str, Any]:
        sql = text("""
            SELECT id, "weekNumber", "startDate", "endDate"
            FROM "Week"
            WHERE "leagueId" = :leagueId
              AND "weekNumber" = :weekNumber
        """)
        with self.db.begin() as conn:
            row = conn.execute(
                sql,
                {"leagueId": league_id, "weekNumber": week_number},
            ).fetchone()

        if not row:
            raise ValueError(f"Week {week_number} not found for league {league_id}")

        return dict(row._mapping)

    def _get_league_members(self, league_id: int) -> List[Dict[str, Any]]:
        sql = text("""
            SELECT id, "teamName"
            FROM "LeagueMember"
            WHERE "leagueId" = :leagueId
            ORDER BY id
        """)
        with self.db.begin() as conn:
            rows = conn.execute(sql, {"leagueId": league_id}).fetchall()
        return [dict(r._mapping) for r in rows]

    def _delete_existing_weekly_scores(self, league_id: int, week_id: int) -> None:
        sql = text("""
            DELETE FROM "WeeklyTeamScore"
            WHERE "leagueId" = :leagueId
              AND "weekId" = :weekId
        """)
        with self.db.begin() as conn:
            conn.execute(sql, {"leagueId": league_id, "weekId": week_id})

    # ------------------------------------------------------------------
    # SportSeason & ownership helpers (for season-level tiebreakers)
    # ------------------------------------------------------------------

    def _get_sport_season_for_league(self, league_id: int) -> Dict[str, Any]:
        """
        Look up the SportSeason row that matches League.sport + League.seasonYear.
        """
        sql = text("""
            SELECT
              ss.id          AS "sportSeasonId",
              ss."sportId"   AS "sportId",
              ss."seasonYear" AS "seasonYear"
            FROM "League" l
            JOIN "SportSeason" ss
              ON ss."sportId"    = l."sport"
             AND ss."seasonYear" = l."seasonYear"
            WHERE l.id = :leagueId
            LIMIT 1
        """)
        with self.db.begin() as conn:
            row = conn.execute(sql, {"leagueId": league_id}).fetchone()

        if not row:
            raise ValueError(f"SportSeason not found for league {league_id}")

        return dict(row._mapping)

    def _get_member_owned_team_ids(self, league_id: int, member_id: int) -> List[int]:
        """
        All SportTeam ids ever owned in this league by this member (any week).
        Used for season-level tiebreakers where we don't care about weekly windows.
        """
        sql = text("""
            SELECT DISTINCT lts."sportTeamId"
            FROM "LeagueTeamSlot" lts
            WHERE lts."leagueId" = :leagueId
              AND lts."memberId" = :memberId
        """)
        with self.db.begin() as conn:
            rows = conn.execute(
                sql, {"leagueId": league_id, "memberId": member_id}
            ).fetchall()
        return [int(r[0]) for r in rows]

    # ------------------------------------------------------------------
    # Weekly scoring: point differential + waterfall + tiebreakers
    # ------------------------------------------------------------------

    def compute_member_point_diff_for_week(
        self,
        league_id: int,
        member_id: int,
        week_number: int,
    ) -> int:
        """
        Sum memberPointDiff across all games for this member in this week.

        Uses ScheduleModel.get_member_games_for_week, which must return rows with:
          - memberPointDiff: int (0 for double-owned, +diff for owned side)
        """
        games = self.schedule_model.get_member_games_for_week(
            league_id=league_id,
            member_id=member_id,
            week_number=week_number,
        )

        total = 0
        for g in games:
            total += int(g["memberPointDiff"])
        return total

    def compute_weekly_scores(self, league_id: int, week_number: int) -> Dict[str, Any]:
        """
        Compute weekly scores for all members in a league for a given week:

        - Uses global GameResult via ScheduleModel
        - Everyone-vs-everyone
        - Waterfall points: N, N-1, ..., 1
        - Applies weekly tiebreakers to break ties in pointDifferential:
            1) weekly head-to-head PD
            2) biggest single-game margin
            3) split (no change)
        - Writes into WeeklyTeamScore.
        """
        week = self._get_week_by_number(league_id, week_number)
        week_id = int(week["id"])

        members = self._get_league_members(league_id)
        if not members:
            raise ValueError(f"No members found for league {league_id}")

        # Compute pure point differential
        member_scores: List[Dict[str, Any]] = []
        for m in members:
            member_id = int(m["id"])
            pdiff = self.compute_member_point_diff_for_week(
                league_id=league_id,
                member_id=member_id,
                week_number=week_number,
            )
            member_scores.append(
                {
                    "memberId": member_id,
                    "teamName": m["teamName"],
                    "pointDifferential": pdiff,
                }
            )

        # Sort by raw PD desc, then memberId for determinism
        member_scores.sort(
            key=lambda x: (-x["pointDifferential"], int(x["memberId"]))
        )

        # Apply weekly tiebreakers within tie groups
        member_scores = self.apply_weekly_tiebreakers(
            league_id=league_id,
            week_number=week_number,
            members=member_scores,
        )

        # Assign waterfall points based on final order
        num_members = len(member_scores)
        for idx, ms in enumerate(member_scores):
            rank = idx + 1
            points_awarded = num_members - idx  # waterfall N..1
            ms["rank"] = rank
            ms["pointsAwarded"] = points_awarded

        # Persist to WeeklyTeamScore (replace existing rows for this league+week)
        self._delete_existing_weekly_scores(league_id, week_id)
        insert_sql = text("""
            INSERT INTO "WeeklyTeamScore"
                ("leagueId", "weekId", "memberId",
                 "pointDifferential", rank, "pointsAwarded")
            VALUES
                (:leagueId, :weekId, :memberId,
                 :pointDifferential, :rank, :pointsAwarded)
        """)

        with self.db.begin() as conn:
            for ms in member_scores:
                conn.execute(
                    insert_sql,
                    {
                        "leagueId": league_id,
                        "weekId": week_id,
                        "memberId": ms["memberId"],
                        "pointDifferential": ms["pointDifferential"],
                        "rank": ms["rank"],
                        "pointsAwarded": ms["pointsAwarded"],
                    },
                )

        return {
            "leagueId": league_id,
            "weekNumber": week_number,
            "weekId": week_id,
            "scores": member_scores,
        }

    # ------------------------------------------------------------------
    # Weekly tiebreakers
    # ------------------------------------------------------------------

    def apply_weekly_tiebreakers(
        self,
        league_id: int,
        week_number: int,
        members: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        For each tie group (same pointDifferential), apply:

          1) head-to-head point differential
          2) biggest single-game margin
          3) split (leave as-is)
        """
        i = 0
        while i < len(members):
            j = i + 1
            while (
                j < len(members)
                and members[j]["pointDifferential"] == members[i]["pointDifferential"]
            ):
                j += 1

            if j - i > 1:
                tied_group = members[i:j]
                resolved = self._resolve_weekly_ties(
                    league_id, week_number, tied_group
                )
                members[i:j] = resolved

            i = j

        return members

    def _resolve_weekly_ties(
        self,
        league_id: int,
        week_number: int,
        group: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        # 1) head-to-head point differential
        result = self._tb_weekly_head_to_head(league_id, week_number, group)
        if result is not None:
            return result

        # 2) biggest single-game margin
        result = self._tb_weekly_biggest_single_margin(
            league_id, week_number, group
        )
        if result is not None:
            return result

        # 3) split: leave as-is
        return group

    def _tb_weekly_head_to_head(
        self,
        league_id: int,
        week_number: int,
        group: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]] | None:
        """
        For all tied members in group:
          - For each pair (A,B), get all head-to-head games in this week
          - Sum point differential for each member
          - Sort group by total head-to-head PD (desc)

        Requires ScheduleModel.get_head_to_head_games(
            league_id, member_a_id, member_b_id, week_number
        ) returning rows with:
          - homeScore, awayScore
          - homeOwnedByA, awayOwnedByA
          - homeOwnedByB, awayOwnedByB
        """
        totals: Dict[int, int] = {int(m["memberId"]): 0 for m in group}
        member_ids = list(totals.keys())

        for i, a_id in enumerate(member_ids):
            for b_id in member_ids[i + 1 :]:
                games = self.schedule_model.get_head_to_head_games(
                    league_id=league_id,
                    member_a_id=a_id,
                    member_b_id=b_id,
                    week_number=week_number,
                )

                a_pd = 0
                b_pd = 0
                for g in games:
                    home_score = int(g["homeScore"])
                    away_score = int(g["awayScore"])

                    if g.get("homeOwnedByA"):
                        a_pd += home_score - away_score
                    if g.get("awayOwnedByA"):
                        a_pd += away_score - home_score

                    if g.get("homeOwnedByB"):
                        b_pd += home_score - away_score
                    if g.get("awayOwnedByB"):
                        b_pd += away_score - home_score

                totals[a_id] += a_pd
                totals[b_id] += b_pd

        if len(set(totals.values())) <= 1:
            return None

        sorted_group = sorted(
            group,
            key=lambda m: (-totals[int(m["memberId"])], int(m["memberId"])),
        )
        return sorted_group

    def _tb_weekly_biggest_single_margin(
        self,
        league_id: int,
        week_number: int,
        group: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]] | None:
        """
        For each tied member:
          - Look at all their games that week
          - Take max(abs(memberPointDiff)) across games
          - Higher wins
        """
        margins: Dict[int, int] = {}

        for m in group:
            member_id = int(m["memberId"])
            games = self.schedule_model.get_member_games_for_week(
                league_id=league_id,
                member_id=member_id,
                week_number=week_number,
            )
            biggest = 0
            for g in games:
                diff = int(g["memberPointDiff"])
                if abs(diff) > biggest:
                    biggest = abs(diff)
            margins[member_id] = biggest

        if len(set(margins.values())) <= 1:
            return None

        sorted_group = sorted(
            group,
            key=lambda m: (-margins[int(m["memberId"])], int(m["memberId"])),
        )
        return sorted_group

    # ------------------------------------------------------------------
    # Season standings + season tiebreakers
    # ------------------------------------------------------------------

    def compute_end_of_year_season_standings(self, league_id: int) -> Dict[str, Any]:
        """
        Aggregate WeeklyTeamScore + computed bonuses for a league:

        - weeklyPoints = sum of WeeklyTeamScore.pointsAwarded
        - bonusPoints  = computed via bonus handlers based on League.settings.bonuses
        - totalPoints  = weeklyPoints + bonusPoints
        - Apply season tiebreakers within ties on totalPoints.
        """
        sql = text("""
            SELECT
            lm.id         AS "memberId",
            lm."teamName" AS "teamName",
            COALESCE(SUM(wts."pointsAwarded"), 0) AS "weeklyPoints"
            FROM "LeagueMember" lm
            LEFT JOIN "WeeklyTeamScore" wts
            ON wts."memberId" = lm.id
            AND wts."leagueId" = lm."leagueId"
            WHERE lm."leagueId" = :leagueId
            GROUP BY lm.id, lm."teamName"
        """)

        with self.db.begin() as conn:
            rows = list(conn.execute(sql, {"leagueId": league_id}))

        # Extract the member IDs from the query so bonus logic knows who exists
        member_ids: List[int] = [int(r._mapping["memberId"]) for r in rows]

        # Compute all bonus points for these members
        bonus_points_by_member: Dict[int, float] = self._compute_bonus_points(
            league_id,
            member_ids,
        )

        # Build standings list
        members: List[Dict[str, Any]] = []
        for r in rows:
            m = r._mapping
            member_id = int(m["memberId"])
            weekly = float(m["weeklyPoints"])
            bonus = float(bonus_points_by_member.get(member_id, 0.0))
            total = weekly + bonus

            members.append(
                {
                    "memberId": member_id,
                    "teamName": m["teamName"],
                    "weeklyPoints": weekly,
                    "bonusPoints": bonus,
                    "totalPoints": total,
                }
            )

        # Initial sort: by total desc, then weekly desc, then memberId asc for stability
        members.sort(
            key=lambda x: (-x["totalPoints"], -x["weeklyPoints"], int(x["memberId"]))
        )

        # Apply season tiebreakers within ties on totalPoints
        members = self._apply_season_tiebreakers(league_id, members)

        return {
            "leagueId": league_id,
            "members": members,
        }


    # ---------- season tiebreaker engine ----------

    def _apply_season_tiebreakers(
        self,
        league_id: int,
        standings: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        For each tie group on totalPoints, apply:

          1) playoff depth in primary postseason (e.g. main playoff bracket)
          2) number of segment/subdivision playoff champions (e.g. conference tournaments)
          3) head-to-head in primary postseason
          4) head-to-head in segment/subdivision postseason
          5) latest non-tied week
        """
        i = 0
        while i < len(standings):
            j = i + 1
            while (
                j < len(standings)
                and standings[j]["totalPoints"] == standings[i]["totalPoints"]
            ):
                j += 1

            if j - i > 1:
                tied_group = standings[i:j]
                resolved = self._resolve_season_ties(league_id, tied_group)
                standings[i:j] = resolved

            i = j

        return standings

    def _resolve_season_ties(
        self,
        league_id: int,
        group: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        # 1) playoff depth (national tournament)
        result = self._tb_season_playoff_depth(league_id, group)
        if result is not None:
            return result

        # 2) number of conference tournament champions
        result = self._tb_season_num_segment_champs(league_id, group)
        if result is not None:
            return result

        # 3) playoff head-to-head in national tournament
        result = self._tb_season_playoff_head_to_head(league_id, group)
        if result is not None:
            return result

        # 4) head-to-head in conference tournaments
        result = self._tb_season_segment_postseason_head_to_head(league_id, group)
        if result is not None:
            return result

        # 5) latest non-tied week
        result = self._tb_season_latest_non_tied_week(league_id, group)
        if result is not None:
            return result

        return group

    # ---------- season tiebreakers ----------

    def _tb_season_playoff_depth(
        self,
        league_id: int,
        group: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]] | None:
        """
        Tiebreaker 1: whoever has the team that goes the farthest
        in the primary postseason (e.g. main playoff bracket).

        Uses GameResult.roundOrder as 'depth' within those phases.
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season["sportSeasonId"])

        # All primary-postseason phases for this season
        sql_phase = text("""
            SELECT id
            FROM "SeasonPhase"
            WHERE "sportSeasonId" = :sportSeasonId
              AND type = ANY(:primaryTypes)
        """)
        with self.db.begin() as conn:
            phase_rows = conn.execute(
                sql_phase,
                {
                    "sportSeasonId": sport_season_id,
                    "primaryTypes": self.PRIMARY_POSTSEASON_PHASE_TYPES,
                },
            ).fetchall()

        if not phase_rows:
            return None

        nt_phase_ids = [int(r[0]) for r in phase_rows]

        depths: Dict[int, int] = {}
        for m in group:
            member_id = int(m["memberId"])
            team_ids = self._get_member_owned_team_ids(league_id, member_id)
            if not team_ids:
                depths[member_id] = 0
                continue

            sql_depth = text("""
                SELECT COALESCE(MAX("roundOrder"), 0) AS max_round
                FROM "GameResult"
                WHERE "sportSeasonId" = :sportSeasonId
                  AND "seasonPhaseId" = ANY(:phaseIds)
                  AND "roundOrder" IS NOT NULL
                  AND (
                    "homeTeamId" = ANY(:teamIds)
                    OR "awayTeamId" = ANY(:teamIds)
                  )
            """)
            with self.db.begin() as conn:
                row = conn.execute(
                    sql_depth,
                    {
                        "sportSeasonId": sport_season_id,
                        "phaseIds": nt_phase_ids,
                        "teamIds": team_ids,
                    },
                ).fetchone()

            depths[member_id] = int(row["max_round"]) if row else 0

        if len(set(depths.values())) <= 1:
            return None

        sorted_group = sorted(
            group,
            key=lambda m: (-depths[int(m["memberId"])], int(m["memberId"])),
        )
        return sorted_group

    def _tb_season_num_segment_champs(
        self,
        league_id: int,
        group: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]] | None:
        """
        Tiebreaker 2: whichever member has the most champions
        in segment-level postseason tournaments (e.g. conference tournaments,
        division playoffs, league cups).

        For each SeasonPhase whose type is in SEGMENT_POSTSEASON_PHASE_TYPES:
          - Find final game (max roundOrder)
          - Champion = winner of that game
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season["sportSeasonId"])

        sql_phases = text("""
            SELECT id
            FROM "SeasonPhase"
            WHERE "sportSeasonId" = :sportSeasonId
              AND type = ANY(:segmentTypes)
        """)
        with self.db.begin() as conn:
            phase_rows = conn.execute(
                sql_phases,
                {
                    "sportSeasonId": sport_season_id,
                    "segmentTypes": self.SEGMENT_POSTSEASON_PHASE_TYPES,
                },
            ).fetchall()

        if not phase_rows:
            return None

        phase_ids = [int(r[0]) for r in phase_rows]

        champions: set[int] = set()
        sql_final = text("""
            SELECT "homeTeamId", "awayTeamId", "homeScore", "awayScore"
            FROM "GameResult"
            WHERE "sportSeasonId" = :sportSeasonId
              AND "seasonPhaseId" = :phaseId
              AND "roundOrder" = (
                SELECT MAX("roundOrder")
                FROM "GameResult"
                WHERE "sportSeasonId" = :sportSeasonId
                  AND "seasonPhaseId" = :phaseId
              )
            LIMIT 1
        """)

        with self.db.begin() as conn:
            for pid in phase_ids:
                row = conn.execute(
                    sql_final,
                    {"sportSeasonId": sport_season_id, "phaseId": pid},
                ).fetchone()
                if not row:
                    continue
                home_id, away_id, home_score, away_score = row
                if home_score > away_score:
                    champions.add(int(home_id))
                elif away_score > home_score:
                    champions.add(int(away_id))

        if not champions:
            return None

        champ_counts: Dict[int, int] = {}
        for m in group:
            member_id = int(m["memberId"])
            team_ids = self._get_member_owned_team_ids(league_id, member_id)
            champ_counts[member_id] = len(champions.intersection(set(team_ids)))

        if len(set(champ_counts.values())) <= 1:
            return None

        sorted_group = sorted(
            group,
            key=lambda m: (-champ_counts[int(m["memberId"])], int(m["memberId"])),
        )
        return sorted_group

    # ---------- shared helper for H2H in phases ----------

    def _head_to_head_pd_in_phases(
        self,
        league_id: int,
        group: List[Dict[str, Any]],
        phase_types: List[str],
    ) -> List[Dict[str, Any]] | None:
        """
        Generic helper:
          - For all tied members in group
          - Within SeasonPhase rows whose `type` is in `phase_types`
          - Compute total head-to-head point differential vs other group members.
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season["sportSeasonId"])

        sql_phases = text("""
            SELECT id
            FROM "SeasonPhase"
            WHERE "sportSeasonId" = :sportSeasonId
              AND type = ANY(:types)
        """)
        with self.db.begin() as conn:
            phase_rows = conn.execute(
                sql_phases,
                {"sportSeasonId": sport_season_id, "types": phase_types},
            ).fetchall()

        if not phase_rows:
            return None

        phase_ids = [int(r[0]) for r in phase_rows]

        member_team_ids: Dict[int, List[int]] = {}
        for m in group:
            mid = int(m["memberId"])
            member_team_ids[mid] = self._get_member_owned_team_ids(league_id, mid)

        totals: Dict[int, int] = {int(m["memberId"]): 0 for m in group}
        member_ids = list(totals.keys())

        all_team_ids = sorted(
            {tid for tids in member_team_ids.values() for tid in tids}
        )

        if not all_team_ids:
            return None

        sql_games = text("""
            SELECT
              gr."homeTeamId",
              gr."awayTeamId",
              gr."homeScore",
              gr."awayScore"
            FROM "GameResult" gr
            WHERE gr."sportSeasonId" = :sportSeasonId
              AND gr."seasonPhaseId" = ANY(:phaseIds)
              AND gr."homeTeamId" IS NOT NULL
              AND gr."awayTeamId" IS NOT NULL
              AND (
                gr."homeTeamId" = ANY(:allTeamIds)
                OR gr."awayTeamId" = ANY(:allTeamIds)
              )
        """)

        with self.db.begin() as conn:
            rows = conn.execute(
                sql_games,
                {
                    "sportSeasonId": sport_season_id,
                    "phaseIds": phase_ids,
                    "allTeamIds": all_team_ids,
                },
            ).fetchall()

        for row in rows:
            home_id, away_id, home_score, away_score = row
            home_id = int(home_id)
            away_id = int(away_id)
            home_score = int(home_score)
            away_score = int(away_score)

            home_members = [m for m in member_ids if home_id in member_team_ids[m]]
            away_members = [m for m in member_ids if away_id in member_team_ids[m]]

            for hm in home_members:
                for am in away_members:
                    pd = home_score - away_score
                    totals[hm] += pd
                    totals[am] -= pd

        if len(set(totals.values())) <= 1:
            return None

        sorted_group = sorted(
            group,
            key=lambda m: (-totals[int(m["memberId"])], int(m["memberId"])),
        )
        return sorted_group

    def _tb_season_playoff_head_to_head(
        self,
        league_id: int,
        group: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]] | None:
        """
        Tiebreaker 3: head-to-head performance in primary postseason phases.
        """
        return self._head_to_head_pd_in_phases(
            league_id,
            group,
            phase_types=self.PRIMARY_POSTSEASON_PHASE_TYPES,
        )

    def _tb_season_segment_postseason_head_to_head(
        self,
        league_id: int,
        group: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]] | None:
        """
        Tiebreaker 4: head-to-head performance in segment-level postseason phases
        (e.g. conference tournaments, division playoffs).
        """
        return self._head_to_head_pd_in_phases(
            league_id,
            group,
            phase_types=self.SEGMENT_POSTSEASON_PHASE_TYPES,
        )

    def _tb_season_latest_non_tied_week(
        self,
        league_id: int,
        group: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]] | None:
        """
        Tiebreaker 5: latest non-tied week score.

        Walk weeks from latest -> earliest. For each:
          - Compare WeeklyTeamScore.rank among tied members.
          - If any difference, sort by rank (1 is best) for that week.
        """
        member_ids = [int(m["memberId"]) for m in group]

        sql_weeks = text("""
            SELECT id, "weekNumber"
            FROM "Week"
            WHERE "leagueId" = :leagueId
            ORDER BY "weekNumber" DESC
        """)
        with self.db.begin() as conn:
            weeks = conn.execute(
                sql_weeks, {"leagueId": league_id}
            ).fetchall()

        if not weeks:
            return None

        sql_scores = text("""
            SELECT "memberId", rank
            FROM "WeeklyTeamScore"
            WHERE "leagueId" = :leagueId
              AND "weekId" = :weekId
              AND "memberId" = ANY(:memberIds)
        """)

        for w in weeks:
            week_id = int(w["id"])
            with self.db.begin() as conn:
                rows = conn.execute(
                    sql_scores,
                    {"leagueId": league_id, "weekId": week_id, "memberIds": member_ids},
                ).fetchall()

            if not rows:
                continue

            ranks = {int(r["memberId"]): int(r["rank"]) for r in rows}
            if len(set(ranks.values())) <= 1:
                continue

            sorted_group = sorted(
                group,
                key=lambda m: (
                    ranks.get(int(m["memberId"]), 9999),
                    int(m["memberId"]),
                ),
            )
            return sorted_group

        return None

    def _get_league_bonus_config(
        self,
        league_id: int,
    ) -> Dict[str, Dict[str, float]]:
        """
        Returns the bonuses config for a league.

        Example shape:
        {
          "conferenceChampion": { "first": 1.5, "second": 1.0, "third": 0.5 },
          "conferenceBottom":   { "last": -1.5, "secondLast": -1.0, "thirdLast": -0.5 },
          "playoffDepth":       { "first": 3.0 }
        }
        """
        settings = self._get_league_settings(league_id)
        bonuses = settings.get("bonuses") or {}
        return bonuses

    def _compute_bonus_points(
        self,
        league_id: int,
        member_ids: List[int],
    ) -> Dict[int, float]:
        """
        For the given league and list of member IDs, compute total bonus points
        according to League.settings.bonuses.

        Returns:
            { memberId: total_bonus_points }
        """
        config = self._get_league_bonus_config(league_id)

        # Start everyone at 0 bonus
        totals: Dict[int, float] = {mid: 0.0 for mid in member_ids}

        if not config:
            return totals

        for bonus_code, bonus_cfg in config.items():
            # Map config key -> handler name on this class
            handler_name = self.BONUS_HANDLERS.get(bonus_code)
            if not handler_name:
                # Unknown bonus type, ignore silently
                continue

            handler = getattr(self, handler_name, None)
            if not handler:
                # Mapping exists but method not defined; ignore
                continue

            # Each handler returns a partial contribution: {memberId: points}
            contrib: Dict[int, float] = handler(league_id, member_ids, bonus_cfg or {})

            for mid, pts in contrib.items():
                # Only add for members that actually exist in this league standings
                if mid in totals:
                    totals[mid] = float(totals.get(mid, 0.0)) + float(pts)

        return totals

    def _get_playoff_depth_by_member(
        self,
        league_id: int,
        member_ids: List[int],
    ) -> Dict[int, int]:
        """
        For each member, compute the deepest round reached in primary postseason
        phases by any of their teams.
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season["sportSeasonId"])

        # Find primary postseason phases
        sql_phase = text("""
            SELECT id
            FROM "SeasonPhase"
            WHERE "sportSeasonId" = :sportSeasonId
              AND type = ANY(:primaryTypes)
        """)

        with self.db.begin() as conn:
            phase_rows = conn.execute(
                sql_phase,
                {
                    "sportSeasonId": sport_season_id,
                    "primaryTypes": self.PRIMARY_POSTSEASON_PHASE_TYPES,
                },
            ).fetchall()

        if not phase_rows:
            # No playoffs defined
            return {mid: 0 for mid in member_ids}

        phase_ids = [int(r[0]) for r in phase_rows]

        depths: Dict[int, int] = {mid: 0 for mid in member_ids}

        sql_depth = text("""
            SELECT COALESCE(MAX("roundOrder"), 0) AS max_round
            FROM "GameResult"
            WHERE "sportSeasonId" = :sportSeasonId
              AND "seasonPhaseId" = ANY(:phaseIds)
              AND "roundOrder" IS NOT NULL
              AND (
                "homeTeamId" = ANY(:teamIds)
                OR "awayTeamId" = ANY(:teamIds)
              )
        """)

        for mid in member_ids:
            team_ids = self._get_member_owned_team_ids(league_id, mid)
            if not team_ids:
                depths[mid] = 0
                continue

            with self.db.begin() as conn:
                row = conn.execute(
                    sql_depth,
                    {
                        "sportSeasonId": sport_season_id,
                        "phaseIds": phase_ids,
                        "teamIds": team_ids,
                    },
                ).fetchone()

            depths[mid] = int(row["max_round"]) if row and row["max_round"] is not None else 0

        return depths

    def _bonus_playoff_depth(
        self,
        league_id: int,
        member_ids: List[int],
        config: Dict[str, float],
    ) -> Dict[int, float]:
        """
        Bonus based on how deep a member's teams go in primary postseason.

        Config keys (optional):
          - "first", "second", "third", "fourth", ... -> points

        Only members with depth > 0 can receive points.
        """
        depths = self._get_playoff_depth_by_member(league_id, member_ids)
        results: Dict[int, float] = {mid: 0.0 for mid in member_ids}

        if not member_ids:
            return results

        # Map finishing position -> config key
        POS_KEYS = {
            1: "first",
            2: "second",
            3: "third",
            4: "fourth",
        }

        # Order members by depth desc, tie-break by memberId
        ordered = sorted(member_ids, key=lambda mid: (-depths[mid], mid))

        current_pos = 1
        i = 0
        while i < len(ordered):
            j = i + 1
            # tie group on depth
            while j < len(ordered) and depths[ordered[j]] == depths[ordered[i]]:
                j += 1

            tier_key = POS_KEYS.get(current_pos)
            if tier_key and tier_key in config:
                pts = float(config[tier_key])
                for mid in ordered[i:j]:
                    if depths[mid] > 0:
                        results[mid] += pts

            current_pos += (j - i)
            i = j

        return results

    def _get_segment_champ_counts_by_member(
        self,
        league_id: int,
        member_ids: List[int],
    ) -> Dict[int, int]:
        """
        For each member, count how many segment-level tournaments
        (conference/division/segment playoffs) they won.
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season["sportSeasonId"])

        sql_phases = text("""
            SELECT id
            FROM "SeasonPhase"
            WHERE "sportSeasonId" = :sportSeasonId
              AND type = ANY(:segmentTypes)
        """)

        with self.db.begin() as conn:
            phase_rows = conn.execute(
                sql_phases,
                {
                    "sportSeasonId": sport_season_id,
                    "segmentTypes": self.SEGMENT_POSTSEASON_PHASE_TYPES,
                },
            ).fetchall()

        if not phase_rows:
            return {mid: 0 for mid in member_ids}

        phase_ids = [int(r[0]) for r in phase_rows]

        # Initialize counts
        champ_counts: Dict[int, int] = {mid: 0 for mid in member_ids}

        # Build a quick teamId->memberId mapping for this league
        team_to_member: Dict[int, int] = {}
        for mid in member_ids:
            team_ids = self._get_member_owned_team_ids(league_id, mid)
            for tid in team_ids:
                team_to_member[int(tid)] = mid

        sql_final = text("""
            SELECT "homeTeamId", "awayTeamId", "homeScore", "awayScore"
            FROM "GameResult"
            WHERE "sportSeasonId" = :sportSeasonId
              AND "seasonPhaseId" = :phaseId
              AND "roundOrder" = (
                SELECT MAX("roundOrder")
                FROM "GameResult"
                WHERE "sportSeasonId" = :sportSeasonId
                  AND "seasonPhaseId" = :phaseId
              )
            LIMIT 1
        """)

        with self.db.begin() as conn:
            for pid in phase_ids:
                row = conn.execute(
                    sql_final,
                    {
                        "sportSeasonId": sport_season_id,
                        "phaseId": pid,
                    },
                ).fetchone()

                if not row:
                    continue

                home_id, away_id, home_score, away_score = row
                if home_id is None or away_id is None:
                    continue

                home_id = int(home_id)
                away_id = int(away_id)
                home_score = int(home_score)
                away_score = int(away_score)

                # Determine champion team
                if home_score > away_score:
                    champ_team = home_id
                elif away_score > home_score:
                    champ_team = away_id
                else:
                    # tie / no champion
                    continue

                mid = team_to_member.get(champ_team)
                if mid is not None:
                    champ_counts[mid] += 1

        return champ_counts

    def _bonus_conference_champion(
        self,
        league_id: int,
        member_ids: List[int],
        config: Dict[str, float],
    ) -> Dict[int, float]:
        """
        Bonus based on how many segment-level tournaments a member won.

        Config keys:
          - "first", "second", "third", "fourth", ... -> points
        """
        champ_counts = self._get_segment_champ_counts_by_member(league_id, member_ids)
        results: Dict[int, float] = {mid: 0.0 for mid in member_ids}

        if not member_ids:
            return results

        POS_KEYS = {
            1: "first",
            2: "second",
            3: "third",
            4: "fourth",
        }

        ordered = sorted(
            member_ids,
            key=lambda mid: (-champ_counts[mid], mid),
        )

        current_pos = 1
        i = 0
        while i < len(ordered):
            j = i + 1
            while j < len(ordered) and champ_counts[ordered[j]] == champ_counts[ordered[i]]:
                j += 1

            tier_key = POS_KEYS.get(current_pos)
            if tier_key and tier_key in config:
                pts = float(config[tier_key])
                for mid in ordered[i:j]:
                    if champ_counts[mid] > 0:
                        results[mid] += pts

            current_pos += (j - i)
            i = j

        return results


    def _get_segment_pd_by_member(
        self,
        league_id: int,
        member_ids: List[int],
    ) -> Dict[int, int]:
        """
        For each member, compute total point differential across all
        segment-level postseason games (ConferenceTournament / SegmentPlayoffs).

        PD = (points scored by their teams) - (points allowed).
        """
        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season["sportSeasonId"])

        sql_phases = text("""
            SELECT id
            FROM "SeasonPhase"
            WHERE "sportSeasonId" = :sportSeasonId
              AND type = ANY(:segmentTypes)
        """)

        with self.db.begin() as conn:
            phase_rows = conn.execute(
                sql_phases,
                {
                    "sportSeasonId": sport_season_id,
                    "segmentTypes": self.SEGMENT_POSTSEASON_PHASE_TYPES,
                },
            ).fetchall()

        if not phase_rows:
            return {mid: 0 for mid in member_ids}

        phase_ids = [int(r[0]) for r in phase_rows]

        # Map team -> member
        team_to_member: Dict[int, int] = {}
        for mid in member_ids:
            team_ids = self._get_member_owned_team_ids(league_id, mid)
            for tid in team_ids:
                team_to_member[int(tid)] = mid

        pd_totals: Dict[int, int] = {mid: 0 for mid in member_ids}

        sql_games = text("""
            SELECT
              gr."homeTeamId",
              gr."awayTeamId",
              gr."homeScore",
              gr."awayScore"
            FROM "GameResult" gr
            WHERE gr."sportSeasonId" = :sportSeasonId
              AND gr."seasonPhaseId" = ANY(:phaseIds)
              AND gr."homeTeamId" IS NOT NULL
              AND gr."awayTeamId" IS NOT NULL
        """)

        with self.db.begin() as conn:
            rows = conn.execute(
                sql_games,
                {
                    "sportSeasonId": sport_season_id,
                    "phaseIds": phase_ids,
                },
            ).fetchall()

        for row in rows:
            home_id, away_id, home_score, away_score = row
            if home_id is None or away_id is None:
                continue

            home_id = int(home_id)
            away_id = int(away_id)
            home_score = int(home_score)
            away_score = int(away_score)

            home_mid = team_to_member.get(home_id)
            away_mid = team_to_member.get(away_id)

            if home_mid is not None:
                pd_totals[home_mid] += (home_score - away_score)

            if away_mid is not None:
                pd_totals[away_mid] += (away_score - home_score)

        return pd_totals


    def _bonus_conference_bottom(
        self,
        league_id: int,
        member_ids: List[int],
        config: Dict[str, float],
    ) -> Dict[int, float]:
        """
        Negative bonus (penalty) for poor performance in segment-level tournaments.

        Config keys:
          - "last", "secondLast", "thirdLast", ... -> negative points

        We rank members by total segment-tournament PD (worst = most negative).
        """
        pd_totals = self._get_segment_pd_by_member(league_id, member_ids)
        results: Dict[int, float] = {mid: 0.0 for mid in member_ids}

        if not member_ids:
            return results

        # Position from bottom -> config key
        NEG_POS_KEYS = {
            1: "last",
            2: "secondLast",
            3: "thirdLast",
            4: "fourthLast",
        }

        # Sort ascending by PD: worst (most negative) first
        ordered = sorted(
            member_ids,
            key=lambda mid: (pd_totals[mid], mid),
        )

        current_pos = 1
        i = 0
        while i < len(ordered):
            j = i + 1
            while j < len(ordered) and pd_totals[ordered[j]] == pd_totals[ordered[i]]:
                j += 1

            tier_key = NEG_POS_KEYS.get(current_pos)
            if tier_key and tier_key in config:
                pts = float(config[tier_key])
                for mid in ordered[i:j]:
                    # Only penalize if they actually played at least one segment game.
                    # You could track "games played" if you want this check stronger.
                    if pd_totals[mid] != 0:
                        results[mid] += pts

            current_pos += (j - i)
            i = j

        return results


    def get_weekly_points_awarded_for_league(
        self,
        league_id: int,
        week_numbers: List[int],
    ) -> List[Dict[str, Any]]:
        if not week_numbers:
            return []

        # normalize: int + unique + sorted (optional but nice)
        week_numbers = sorted({int(w) for w in week_numbers})

        sql = text("""
            SELECT
            w."weekNumber",
            w."startDate",
            w."endDate",
            wts."memberId",
            lm."teamName",
            wts."pointsAwarded",
            wts."pointDifferential",
            wts.rank
            FROM "WeeklyTeamScore" wts
            JOIN "Week" w
            ON w.id = wts."weekId"
            JOIN "LeagueMember" lm
            ON lm.id = wts."memberId"
            WHERE wts."leagueId" = :leagueId
            AND w."weekNumber" IN :weekNumbers
            ORDER BY w."weekNumber" ASC, wts.rank ASC;
        """).bindparams(bindparam("weekNumbers", expanding=True))

        with self.db.connect() as conn:
            rows = conn.execute(
                sql,
                {"leagueId": league_id, "weekNumbers": week_numbers},
            ).fetchall()

        return [dict(r._mapping) for r in rows]