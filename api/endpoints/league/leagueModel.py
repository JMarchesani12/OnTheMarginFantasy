import datetime as dt
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from endpoints.schedule.scheduleModel import ScheduleModel
from utils.authorization import league_read_scope
from .admission_service import AdmissionService
from .member_service import MemberService
from .league_admin_service import LeagueAdminService
from .league_read_service import LeagueReadService
from .member_repository import ALLOWED_LEAGUE_MEMBER_FIELDS
from .contracts import AdmissionDenied, AdmissionRejected
from rules.leagueRules import get_timezone_name_from_settings, validate_timezone_name, ensure_timezone_in_settings



class LeagueModel:
    def __init__(self, db: Engine):
        self.db = db
        self.scheduleModel = ScheduleModel(db, os.getenv("ESPN_BASE_URL"))

    @staticmethod
    def _league_read_scope(league_id: int, reader_user_id: Optional[int]):
        return league_read_scope(league_id, reader_user_id)

    def get_league_read_access(self, league_id: int, user_id: int):
        return LeagueReadService(self.db).access_for_reader_id(league_id, user_id)

    def get_member_previews_for_user(self, league_id: int, user_id: int):
        return LeagueReadService(self.db).member_previews_for_reader_id(league_id, user_id)

    def sync_due_league_statuses(self) -> None:
        """
        Keep League.status aligned with draft state and season dates.

        DraftState live/paused owns Drafting. Completed seasons win last so old
        leagues cannot be moved back by a stale draft state.
        """
        with self.db.begin() as conn:
            conn.execute(
                text("""
                    UPDATE "League" l
                    SET status = 'Pre-Draft',
                        "updatedAt" = now()
                    WHERE l."draftDate" IS NOT NULL
                      AND now() < l."draftDate"
                      AND l.status <> 'Pre-Draft'
                      AND NOT EXISTS (
                        SELECT 1
                        FROM "DraftState" ds
                        WHERE ds."leagueId" = l.id
                          AND ds.status IN ('live', 'paused', 'complete')
                      )
                """)
            )

            conn.execute(
                text("""
                    UPDATE "League" l
                    SET status = 'Drafting',
                        "updatedAt" = now()
                    FROM "DraftState" ds
                    WHERE ds."leagueId" = l.id
                      AND ds.status IN ('live', 'paused')
                      AND l.status <> 'Drafting'
                """)
            )

            conn.execute(
                text("""
                    UPDATE "League" l
                    SET status = 'Post-Draft',
                        "updatedAt" = now()
                    FROM "DraftState" ds, "SportSeason" ss
                    WHERE ds."leagueId" = l.id
                      AND ss."sportId" = l.sport
                      AND ss."seasonYear" = l."seasonYear"
                      AND ds.status = 'complete'
                      AND now()::date < ss."seasonStart"::date
                      AND l.status <> 'Post-Draft'
                """)
            )

            conn.execute(
                text("""
                    UPDATE "League" l
                    SET status = 'In-Season',
                        "updatedAt" = now()
                    FROM "SportSeason" ss
                    WHERE ss."sportId" = l.sport
                      AND ss."seasonYear" = l."seasonYear"
                      AND now()::date >= ss."seasonStart"::date
                      AND now()::date <= ss."seasonEnd"::date
                      AND l.status NOT IN ('Drafting', 'In-Season', 'Completed')
                      AND NOT EXISTS (
                        SELECT 1
                        FROM "DraftState" ds
                        WHERE ds."leagueId" = l.id
                          AND ds.status IN ('live', 'paused')
                      )
                """)
            )

            conn.execute(
                text("""
                    UPDATE "League" l
                    SET status = 'Completed',
                        "updatedAt" = now()
                    FROM "SportSeason" ss
                    WHERE ss."sportId" = l.sport
                      AND ss."seasonYear" = l."seasonYear"
                      AND now()::date > ss."seasonEnd"::date
                      AND l.status <> 'Completed'
                """)
            )

    def _get_timezone_name_from_settings(self, settings: Dict[str, Any]) -> Optional[str]:
        return get_timezone_name_from_settings(settings)

    def _validate_timezone_name(self, tz_name: str) -> None:
        validate_timezone_name(tz_name)

    def _ensure_timezone_in_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        return ensure_timezone_in_settings(settings)

    def get_league(self, leagueId, reader_user_id: Optional[int] = None):
        scope, reader_params = self._league_read_scope(leagueId, reader_user_id)
        self.sync_due_league_statuses()

        with self.db.begin() as conn:
            league = conn.execute(
                text(f"""
                    SELECT
                        l.*,
                        w.id AS "currentWeekId",
                        w."weekNumber" AS "currentWeekNumber",
                        w."startDate" AS "currentWeekStartDate",
                        w."endDate" AS "currentWeekEndDate"
                    FROM "League" l
                    LEFT JOIN "Week" w
                      ON w."leagueId" = l.id
                     AND now() >= COALESCE(
                        w."startDate",
                        w."endDate" + interval '1 microsecond' - interval '7 days'
                     )
                     AND now() <= w."endDate"
                    WHERE l.id = :leagueId
                    {scope}
                    ORDER BY w."weekNumber" DESC NULLS LAST
                    LIMIT 1
                """),
                {"leagueId": leagueId, **reader_params}
            ).fetchone()

        return dict(league._mapping) if league else None

    def get_league_rules(self, league_id, reader_user_id: Optional[int] = None):
        service = LeagueReadService(self.db)
        if reader_user_id is None:
            return service.rules_for_job(league_id)
        return service.rules_for_reader_id(league_id, reader_user_id)

    def create_league(self, league: Dict[str, Any]) -> Dict[str, Any]:
        # Make a copy so we don't mutate the original dict
        return LeagueAdminService(self.db).create_for_job(
            league, lambda league_id: self.scheduleModel.ensure_weeks_for_league(league_id),
        )
    
    def update_league(self, league_id: int, patch: Dict[str, Any]) -> Dict[str, Any]:
        """Trusted model entry point; interactive HTTP must use the checked variant."""
        return self._update_league(league_id, patch)

    def update_league_as_commissioner(
        self, league_id: int, user_id: int, patch: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Update as a verified HTTP principal; caller supplies resolved user_id."""
        return self._update_league(league_id, patch, commissioner_id=user_id)

    def _update_league(
        self, league_id: int, patch: Dict[str, Any], commissioner_id: int | None = None,
    ) -> Dict[str, Any]:
        service = LeagueAdminService(self.db)
        if commissioner_id is None:
            return service.update_for_job(league_id, patch)
        return service.update_for_legacy_commissioner(league_id, commissioner_id, patch)

    
    # 1) All leagues a user is in
    def get_leagues_for_user(self, user_id: int, stage: str = "all") -> List[Dict[str, Any]]:
        """
        stage: "all" | "active" | "completed"
        - all: no additional status filter
        - active: status != 'completed'
        - completed: status = 'completed'
        """

        stage = (stage or "all").lower()
        if stage not in ("all", "active", "completed"):
            stage = "all"

        self.sync_due_league_statuses()

        base_sql = """
            SELECT
            -- League fields
            l.id                AS "leagueId",
            l."createdAt"       AS "leagueCreatedAt",
            l."name"            AS "leagueName",
            l."numPlayers"      AS "numPlayers",
            l.status            AS "status",
            l."updatedAt"       AS "updatedAt",
            l."draftDate"       AS "draftDate",
            l."tradeDeadline"   AS "tradeDeadline",
            l."freeAgentDeadline" AS "freeAgentDeadline",
            l."seasonYear"      AS "seasonYear",
            l."settings"        AS "settings",

            -- Commissioner info
            cu."displayName"    AS "commissionerDisplayName",
            cu."id"             AS "commissionerId",

            -- Sport info
            s.name              AS "sport",
            s."maxPlayersToHaveMaxRounds" AS "maxPlayersToHaveMaxRounds",

            -- Member-specific fields for this user
            lm.id               AS "memberId",
            lm."teamName"       AS "teamName",
            lm."draftOrder"     AS "draftOrder",
            COALESCE(sp."seasonPoints", lm."seasonPoints", 0) AS "seasonPoints",

            -- Current week info (nullable if no matching week)
            w.id                AS "currentWeekId",
            w."weekNumber"      AS "currentWeekNumber",
            w."startDate"       AS "currentWeekStartDate",
            w."endDate"         AS "currentWeekEndDate"

            FROM "LeagueMember" lm
            JOIN "League"      l  ON l.id = lm."leagueId"
            JOIN "Sport"       s  ON s.id = l."sport"
            JOIN "User"        cu ON cu.id = l.commissioner
            LEFT JOIN (
                SELECT
                    wts."leagueId",
                    wts."memberId",
                    SUM(wts."pointsAwarded") AS "seasonPoints"
                FROM "WeeklyTeamScore" wts
                JOIN "Week" w
                  ON w.id = wts."weekId"
                 AND w."weekNumber" >= 0
                GROUP BY wts."leagueId", wts."memberId"
            ) sp
            ON sp."leagueId" = lm."leagueId"
            AND sp."memberId" = lm.id

            LEFT JOIN "Week"   w
            ON w."leagueId" = l.id
            AND now() >= COALESCE(
                w."startDate",
                w."endDate" + interval '1 microsecond' - interval '7 days'
            )
            AND now() <= w."endDate"

            WHERE lm."userId" = :user_id
        """

        if stage == "active":
            base_sql += " AND l.status <> 'Completed'"
        elif stage == "completed":
            base_sql += " AND l.status = 'Completed'"

        base_sql += ' ORDER BY l.id, lm."draftOrder"'

        sql = text(base_sql)

        with self.db.connect() as conn:
            result = conn.execute(sql, {"user_id": user_id})
            rows = [dict(r._mapping) for r in result]

        logging.debug(
            "get_leagues_for_user(user_id=%s, stage=%s) -> %d rows",
            user_id,
            stage,
            len(rows),
        )
        return rows


    def get_members_for_league(self, league_id: int, reader_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        scope, reader_params = self._league_read_scope(league_id, reader_user_id)
        sql = text(
            f"""
            SELECT
              lm.id               AS "memberId",
              lm."createdAt"      AS "memberCreatedAt",
              lm."leagueId"       AS "leagueId",
              lm."userId"         AS "userId",
              lm."teamName"       AS "teamName",
              lm."draftOrder"     AS "draftOrder",
              COALESCE(sp."seasonPoints", lm."seasonPoints", 0) AS "seasonPoints",
              u."displayName"     AS "displayName"
            FROM "LeagueMember" lm
            JOIN "User" u on u.id = lm."userId"
            LEFT JOIN (
                SELECT
                    wts."leagueId",
                    wts."memberId",
                    SUM(wts."pointsAwarded") AS "seasonPoints"
                FROM "WeeklyTeamScore" wts
                JOIN "Week" w
                  ON w.id = wts."weekId"
                 AND w."weekNumber" >= 0
                GROUP BY wts."leagueId", wts."memberId"
            ) sp
            ON sp."leagueId" = lm."leagueId"
            AND sp."memberId" = lm.id
            WHERE lm."leagueId" = :league_id
            {scope}
            ORDER BY lm."draftOrder", lm.id
            """
        )

        current_week_sql = text(f"""
            SELECT w."weekNumber", w."startDate", w."endDate"
            FROM "Week" w
            WHERE w."leagueId" = :league_id
              {scope}
              AND now() >= COALESCE(
                w."startDate",
                w."endDate" + interval '1 microsecond' - interval '7 days'
              )
              AND now() <= w."endDate"
            ORDER BY w."weekNumber" DESC
            LIMIT 1
        """)

        with self.db.connect() as conn:
            result = conn.execute(sql, {"league_id": league_id, **reader_params})
            rows = [dict(r._mapping) for r in result]
            current_week_row = conn.execute(
                current_week_sql,
                {"league_id": league_id, **reader_params},
            ).fetchone()

        current_week_number = None
        current_week_start = None
        current_week_end = None
        if current_week_row:
            current_week_number = int(current_week_row[0])
            current_week_start = current_week_row[1]
            current_week_end = current_week_row[2]

        members: List[Dict[str, Any]] = []
        local_tz = self.scheduleModel._get_league_timezone(league_id)
        date_keys: List[dt.date] = []
        if current_week_start and current_week_end:
            start_dt = current_week_start
            end_dt = current_week_end
            if isinstance(start_dt, str):
                start_dt = dt.datetime.fromisoformat(start_dt)
            if isinstance(end_dt, str):
                end_dt = dt.datetime.fromisoformat(end_dt)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=dt.timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=dt.timezone.utc)
            cur_date = start_dt.astimezone(local_tz).date()
            end_date = end_dt.astimezone(local_tz).date()
            while cur_date <= end_date:
                date_keys.append(cur_date)
                cur_date = cur_date + dt.timedelta(days=1)

        for r in rows:
            member_id = r["memberId"]
            current_week_point_differential = 0
            daily_point_differentials: List[Dict[str, Any]] = []
            if current_week_number is not None:
                games = self.scheduleModel.get_member_games_for_week(
                    league_id=league_id,
                    member_id=member_id,
                    week_number=current_week_number,
                )
                daily_totals = {d: 0 for d in date_keys}
                for g in games:
                    current_week_point_differential += int(g["memberPointDiff"])
                    game_dt = g.get("date")
                    if game_dt is None:
                        continue
                    if isinstance(game_dt, str):
                        game_dt = dt.datetime.fromisoformat(game_dt)
                    if game_dt.tzinfo is None:
                        game_dt = game_dt.replace(tzinfo=dt.timezone.utc)
                    game_date = game_dt.astimezone(local_tz).date()
                    if game_date in daily_totals:
                        daily_totals[game_date] += int(g["memberPointDiff"])
                daily_point_differentials = [
                    {"date": d.isoformat(), "pointDifferential": daily_totals[d]}
                    for d in date_keys
                ]

            members.append(
                {
                    "id": r["memberId"],
                    "createdAt": r["memberCreatedAt"],
                    "leagueId": r["leagueId"],
                    "userId": r["userId"],
                    "teamName": r["teamName"],
                    "draftOrder": r["draftOrder"],
                    "seasonPoints": r["seasonPoints"],
                    "displayName": r['displayName'],
                    "currentWeekPointDifferential": current_week_point_differential,
                    "dailyPointDifferentials": daily_point_differentials,
                }
            )

        return members

    def get_league_conferences(self, league_id: int, reader_user_id: Optional[int] = None) -> Dict[str, Any]:
        service = LeagueReadService(self.db)
        if reader_user_id is None:
            return service.conferences_for_job(league_id)
        return service.conferences_for_reader_id(league_id, reader_user_id)
    
    def _get_league_commissioner(self, league_id: int) -> Optional[int]:
        return AdmissionService(self.db).get_commissioner_for_job(league_id)

    def _ensure_commissioner(self, league_id: int, acting_user_id: int) -> None:
        commissioner = self._get_league_commissioner(league_id)
        if commissioner is None:
            raise ValueError(f"League {league_id} not found")
        if commissioner != acting_user_id:
            raise PermissionError("Only the commissioner can perform this action")
        

    def create_join_request(self, league_id: int, user_id: int, message: Optional[str] = None, team_name: Optional[str] = None) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).create_request_for_user_id(user_id, league_id, message, team_name)
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def list_join_requests(self, league_id: int, status: Optional[str] = None) -> list[Dict[str, Any]]:
        """Trusted model listing; HTTP must use the commissioner-checked variant."""
        return self._list_join_requests(league_id, status)

    def list_join_requests_as_commissioner(
        self, league_id: int, user_id: int, status: Optional[str] = None,
    ) -> list[Dict[str, Any]]:
        try:
            return AdmissionService(self.db).list_requests_for_legacy_reader(user_id, league_id, status)
        except AdmissionDenied as exc:
            raise PermissionError(str(exc)) from exc
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def _list_join_requests(
        self, league_id: int, status: Optional[str], commissioner_id: int | None = None,
    ) -> list[Dict[str, Any]]:
        service = AdmissionService(self.db)
        if commissioner_id is None:
            return service.list_requests_for_job(league_id, status)
        return service.list_requests_for_legacy_scope(commissioner_id, league_id, status)

    def approve_join_request(self, league_id: int, request_id: int, acting_user_id: int) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).approve_request_for_job(league_id, request_id, acting_user_id)
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def approve_join_request_as_commissioner(
        self, league_id: int, request_id: int, user_id: int,
    ) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).approve_request_for_legacy_commissioner(user_id, league_id, request_id)
        except AdmissionDenied as exc:
            raise PermissionError(str(exc)) from exc
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def _approve_join_request(
        self, conn, league_id: int, request_id: int, acting_user_id: int,
    ) -> Dict[str, Any]:
        # lock the request row to prevent double-approval races
        try:
            return AdmissionService(self.db).approve_request_in_transaction(conn, league_id, request_id, acting_user_id)
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def deny_join_request(self, league_id: int, request_id: int, acting_user_id: int) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).deny_request_for_job(league_id, request_id, acting_user_id)
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def deny_join_request_as_commissioner(
        self, league_id: int, request_id: int, user_id: int,
    ) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).deny_request_for_legacy_commissioner(user_id, league_id, request_id)
        except AdmissionDenied as exc:
            raise PermissionError(str(exc)) from exc
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def _deny_join_request(
        self, conn, league_id: int, request_id: int, acting_user_id: int,
    ) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).deny_request_in_transaction(conn, league_id, request_id, acting_user_id)
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc

    def cancel_join_request(self, league_id: int, request_id: int, user_id: int) -> Dict[str, Any]:
        try:
            return AdmissionService(self.db).cancel_request_for_owner_id(user_id, league_id, request_id)
        except AdmissionDenied as exc:
            raise PermissionError(str(exc)) from exc
        except AdmissionRejected as exc:
            raise ValueError(str(exc)) from exc
    
    def remove_member_and_shift_draft_order(
        self,
        league_id: int,
        member_id: int,
        acting_user_id: int,
        shift_draft_order: bool = True,
    ) -> Dict[str, Any]:
        return MemberService(self.db).remove_for_legacy_commissioner(
            league_id, member_id, acting_user_id, shift_draft_order,
        )
    
    def search_leagues(
        self,
        q: str,
        sport_id: int | None = None,
        limit: int = 20,
        offset: int = 0,
    ):
        return LeagueReadService(self.db).search_public(q, sport_id, limit, offset)

    def delete_league(self, league_id: int, acting_user_id: int) -> Dict[str, Any]:
        return LeagueAdminService(self.db).delete_for_legacy_commissioner(league_id, acting_user_id)
    
    def update_owned_league_member(
        self, member_id: int, user_id: int, team_name: str,
    ) -> Dict[str, Any]:
        return MemberService(self.db).rename_for_owner_id(member_id, user_id, team_name)

    def update_league_member(self, member_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        # keep only allowed keys that are actually present
        return MemberService(self.db).update_for_job(member_id, updates)
