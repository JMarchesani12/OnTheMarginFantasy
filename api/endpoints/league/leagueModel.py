import datetime as dt
import json
import logging
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine
from zoneinfo import ZoneInfo

from endpoints.schedule.scheduleModel import ScheduleModel
from utils.authorization import league_read_scope
from .admission_service import AdmissionService
from .member_service import MemberService
from .member_repository import ALLOWED_LEAGUE_MEMBER_FIELDS
from .contracts import AdmissionDenied, AdmissionRejected
from rules.leagueRules import settings_for_creation, settings_for_update, describe_rules



class LeagueModel:
    def __init__(self, db: Engine):
        self.db = db
        self.scheduleModel = ScheduleModel(db, os.getenv("ESPN_BASE_URL"))

    @staticmethod
    def _league_read_scope(league_id: int, reader_user_id: Optional[int]):
        return league_read_scope(league_id, reader_user_id)

    def get_league_read_access(self, league_id: int, user_id: int):
        """Fetch only discovery metadata and the caller's full-read entitlement."""
        with self.db.begin() as conn:
            row = conn.execute(text('''
                SELECT l.id, l.name, l.sport, l."isDiscoverable",
                       u."displayName" AS "commissionerDisplayName",
                       CASE WHEN l.commissioner = :userId OR EXISTS (
                           SELECT 1 FROM "LeagueMember" lm
                           WHERE lm."leagueId" = l.id AND lm."userId" = :userId
                       ) THEN true ELSE false END AS "fullAccess"
                FROM "League" l LEFT JOIN "User" u ON u.id = l.commissioner
                WHERE l.id = :leagueId
            '''), {'leagueId': league_id, 'userId': user_id}).mappings().first()
        return dict(row) if row else None

    def get_member_previews_for_user(self, league_id: int, user_id: int):
        """Names only; query rechecks discoverability or caller's own full access."""
        with self.db.begin() as conn:
            rows = conn.execute(text('''
                SELECT lm.id, lm."teamName", u."displayName"
                FROM "LeagueMember" lm
                JOIN "User" u ON u.id = lm."userId"
                JOIN "League" l ON l.id = lm."leagueId"
                WHERE l.id = :leagueId AND (
                    l."isDiscoverable" = true OR l.commissioner = :userId OR EXISTS (
                        SELECT 1 FROM "LeagueMember" reader
                        WHERE reader."leagueId" = l.id AND reader."userId" = :userId
                    )
                )
                ORDER BY lm.id
            '''), {'leagueId': league_id, 'userId': user_id}).mappings().all()
        return [dict(row) for row in rows]

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
        if not isinstance(settings, dict):
            return None

        schedule_cfg = settings.get("schedule") or {}
        if isinstance(schedule_cfg, dict):
            tz_name = schedule_cfg.get("timezone") or schedule_cfg.get("timeZone")
            if tz_name:
                return tz_name

        return settings.get("timezone") or settings.get("timeZone")

    def _validate_timezone_name(self, tz_name: str) -> None:
        try:
            ZoneInfo(tz_name)
        except Exception as exc:
            raise ValueError(f"Invalid timezone: {tz_name}") from exc

    def _ensure_timezone_in_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        tz_name = self._get_timezone_name_from_settings(settings)
        if tz_name:
            self._validate_timezone_name(tz_name)
            return settings

        updated = dict(settings or {})
        updated["timezone"] = "UTC"
        return updated

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
        scope, reader_params = self._league_read_scope(league_id, reader_user_id)
        with self.db.connect() as conn:
            row = conn.execute(text(f'SELECT id, name, sport, "seasonYear", settings, "tradeDeadline", "freeAgentDeadline", "draftDate" FROM "League" WHERE id = :leagueId {scope}'),
                               {'leagueId': league_id, **reader_params}).fetchone()
            if not row:
                return None
            league = dict(row._mapping)
            teams = conn.execute(text("""
                SELECT st.id AS "teamId", st."displayName" AS "teamName",
                    COALESCE(st.tier, (SELECT COALESCE(MAX(t.tier), 0) + 1
                        FROM "SportTeam" t WHERE t."sportId" = :sportId)) AS tier
                FROM "SportTeam" st WHERE st."sportId" = :sportId
                ORDER BY tier, st."displayName"
            """), {'sportId': league['sport']}).fetchall()
        payload = describe_rules(league['sport'], league.get('settings'), [dict(t._mapping) for t in teams])
        payload.update(leagueId=league_id, leagueName=league['name'], seasonYear=league['seasonYear'])
        for key in ('tradeDeadline', 'freeAgentDeadline', 'draftDate'):
            value = league.get(key)
            payload['settings'][key] = value.isoformat() if hasattr(value, 'isoformat') else value
        return payload

    def create_league(self, league: Dict[str, Any]) -> Dict[str, Any]:
        # Make a copy so we don't mutate the original dict
        league = dict(league)

        team_name = league.get("teamName")
        if not isinstance(team_name, str) or not team_name.strip():
            raise ValueError("Team name is required.")
        team_name = team_name.strip()

        settings = settings_for_creation(league['sport'], league.get('settings'))
        league['settings'] = json.dumps(self._ensure_timezone_in_settings(settings))

        sql = text("""
            WITH created AS (
            INSERT INTO "League"
                ("name", sport, "numPlayers", status, settings, "updatedAt", "draftDate", "commissioner", "seasonYear", "isDiscoverable")
            VALUES
                (:name, :sport, :numPlayers, :status, cast(:settings as jsonb), now(), :draftDate, :commissioner, :seasonYear, :isDiscoverable)
            RETURNING
                id, "createdAt", name, sport, "numPlayers", status, settings, "updatedAt", "draftDate", commissioner, "seasonYear", "isDiscoverable"
            )
            SELECT
            c.*,
            to_jsonb(s.*) AS sportInfo
            FROM created c
            JOIN "Sport" s ON s.id = c.sport;
        """)

        with self.db.begin() as conn:
            created_row = conn.execute(sql, league).mappings().first()

            if not created_row:
                raise RuntimeError("Failed to create League")

            created = dict(created_row)

            # Create LeagueMember for commissioner
            lm_sql = text("""
                INSERT INTO "LeagueMember"
                    ("leagueId", "userId", "teamName", "seasonPoints", "draftOrder")
                VALUES
                    (:leagueId, :userId, :teamName, 0, 1)
                RETURNING id
            """)

            lm_row = conn.execute(
                lm_sql,
                {
                    "leagueId": created["id"],
                    "userId": created["commissioner"],
                    "teamName": team_name,
                },
            ).fetchone()

            created["creatorMemberId"] = lm_row._mapping["id"]

        self.scheduleModel.ensure_weeks_for_league(created['id'])

        return created
    
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
        """
        Partially updates a League row.

        - Only updates fields present in `patch`.
        - JSON-encodes settings if dict/list.
        - Always updates "updatedAt" = now().
        """

        # Fetch current settings and check authority before settings validation.
        with self.db.begin() as conn:
            league_row = conn.execute(
                text("""
                    SELECT id, sport, settings, commissioner
                    FROM "League"
                    WHERE id = :leagueId
                """),
                {"leagueId": league_id},
            ).fetchone()

        if not league_row:
            raise ValueError(f"League {league_id} not found")

        if commissioner_id is not None and league_row._mapping['commissioner'] != commissioner_id:
            raise PermissionError("Only the commissioner can perform this action")

        # 2) Allowlist fields you actually want to update
        allowed_fields = {
            "name",
            "numPlayers",
            "status",
            "settings",
            "draftDate",
            "tradeDeadline",
            "freeAgentDeadline"
        }

        patch = dict(patch)
        if "settings" in patch:
            if not isinstance(patch['settings'], dict):
                raise ValueError('League settings must be an object')
            current = dict(league_row._mapping)
            patch['settings'] = settings_for_update(current['sport'], current.get('settings'), patch['settings'])

        if "settings" in patch and isinstance(patch.get("settings"), dict):
            tz_name = self._get_timezone_name_from_settings(patch["settings"])
            if tz_name:
                self._validate_timezone_name(tz_name)

        update_data: Dict[str, Any] = {"leagueId": league_id}
        set_clauses = []

        for key, value in patch.items():
            if key not in allowed_fields:
                continue  # silently ignore unknown fields (or raise)

            if key == "settings" and isinstance(value, (dict, list)):
                value = json.dumps(value)

            update_data[key] = value

            if key == "settings":
                set_clauses.append('settings = cast(:settings as jsonb)')
            else:
                # quote any mixed-case columns
                if key in {"numPlayers", "draftDate", "tradeDeadline", "freeAgentDeadline"}:
                    set_clauses.append(f'"{key}" = :{key}')
                else:
                    set_clauses.append(f'{key} = :{key}')

        # Always update updatedAt
        set_clauses.append('"updatedAt" = now()')

        if len(set_clauses) == 1:
            # Only updatedAt, nothing meaningful to update
            # You can choose to return the current league instead.
            raise ValueError("No valid fields to update")

        ownership_clause = ''
        if commissioner_id is not None:
            update_data['actingUserId'] = commissioner_id
            ownership_clause = 'AND commissioner = :actingUserId'

        sql = text(f"""
            WITH updated AS (
            UPDATE "League"
            SET {", ".join(set_clauses)}
            WHERE id = :leagueId {ownership_clause}
            RETURNING
                id, "createdAt", name, sport, "numPlayers", status, settings, "updatedAt",
                "draftDate", "freeAgentDeadline", "tradeDeadline", commissioner
            )
            SELECT
            u.*,
            to_jsonb(s.*) AS sportInfo
            FROM updated u
            JOIN "Sport" s ON s.id = u.sport;
        """)

        with self.db.begin() as conn:
            updated_row = conn.execute(sql, update_data).mappings().first()

        if not updated_row:
            if commissioner_id is not None:
                raise PermissionError("Only the commissioner can perform this action")
            raise RuntimeError("Failed to update League")

        return dict(updated_row)

    
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
        """
        For a leagueId, returns all SportConference rows for that league's sport,
        joined to base Conference for displayName, plus team counts.
        """

        # IMPORTANT: adjust these column names if your League schema differs
        scope, reader_params = self._league_read_scope(league_id, reader_user_id)
        league_sql = text(f"""
            SELECT
              id AS "leagueId",
              sport AS "sportId",
              "seasonYear" AS "seasonYear"
            FROM "League"
            WHERE id = :leagueId
            {scope}
            LIMIT 1
        """)

        with self.db.begin() as conn:
            league_row = conn.execute(league_sql, {"leagueId": league_id, **reader_params}).fetchone()

            if not league_row:
                raise ValueError(f"League {league_id} not found")

            league = dict(league_row._mapping)
            sport_id = league["sportId"]
            season_year = league.get("seasonYear")

            if season_year is None:
                # If your League table truly doesn't store seasonYear, you can:
                # 1) require it as a query param, OR
                # 2) decide a default.
                # I'm not going to guess—so we fail loudly.
                raise ValueError("League.seasonYear is null/missing; cannot compute season-scoped memberships")

            conf_sql = text("""
                SELECT
                  sc.id AS "sportConferenceId",
                  sc."conferenceId" AS "conferenceId",
                  c.name AS "displayName",
                  sc."maxTeamsPerOwner" AS "maxTeamsPerOwner",
                  COALESCE(t."teamsInConference", 0) AS "teamsInConference"
                FROM "SportConference" sc
                JOIN "Conference" c ON c.id = sc."conferenceId"
                LEFT JOIN (
                  SELECT
                    cm."sportConferenceId",
                    COUNT(*) AS "teamsInConference"
                  FROM "ConferenceMembership" cm
                  WHERE (cm."seasonYear" IS NULL OR cm."seasonYear" = :seasonYear)
                  GROUP BY cm."sportConferenceId"
                ) t ON t."sportConferenceId" = sc.id
                WHERE sc."sportId" = :sportId
                ORDER BY c.name;
            """)

            rows = conn.execute(conf_sql, {"sportId": sport_id, "seasonYear": season_year}).fetchall()

        return {
            "leagueId": league_id,
            "sportId": sport_id,
            "seasonYear": season_year,
            "conferences": [dict(r._mapping) for r in rows],
        }
    
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
        q = (q or "").strip()
        if len(q) < 2:
            return []

        limit = max(1, min(int(limit), 50))
        offset = max(0, int(offset))

        pattern = f"%{q}%"

        params = {
            "pattern": pattern,
            "q": q,
            "limit": limit,
            "offset": offset,
        }

        sport_clause = ""
        if sport_id is not None:
            sport_clause = "AND l.sport = :sportId"
            params["sportId"] = sport_id

        sql = text(f"""
            SELECT
            l.id,
            l.name,
            l.sport,
            l."numPlayers",
            l.status,
            l."draftDate",
            l."isDiscoverable",
            l.commissioner,
            u."displayName" AS "commissionerDisplayName"
            FROM "League" l
            JOIN "User" u ON u.id = l.commissioner
            WHERE l."isDiscoverable" = true
            AND l.name ILIKE :pattern
            {sport_clause}
            ORDER BY similarity(l.name, :q) DESC, l.name ASC
            LIMIT :limit OFFSET :offset
        """)

        with self.db.begin() as conn:
            rows = conn.execute(sql, params).mappings().all()

        return [dict(r) for r in rows]

    def delete_league(self, league_id: int, acting_user_id: int) -> Dict[str, Any]:
        """
        Deletes a league and all dependent data (via ON DELETE CASCADE).

        Only the commissioner is allowed to delete a league.
        This operation is atomic.
        """

        with self.db.begin() as conn:
            # Lock league row
            league = conn.execute(
                text("""
                    SELECT id, name, commissioner
                    FROM "League"
                    WHERE id = :leagueId
                    FOR UPDATE
                """),
                {"leagueId": league_id},
            ).mappings().first()

            if not league:
                raise ValueError("League not found")

            if int(league["commissioner"]) != int(acting_user_id):
                raise PermissionError("Only the commissioner can delete this league")

            # Delete league (cascades to members, join requests, weeks, etc.)
            deleted = conn.execute(
                text("""
                    DELETE FROM "League"
                    WHERE id = :leagueId AND commissioner = :actingUserId
                    RETURNING id, name
                """),
                {"leagueId": league_id, "actingUserId": acting_user_id},
            ).mappings().first()

            if not deleted:
                raise RuntimeError("Failed to delete league")

        return {
            "deletedLeagueId": deleted["id"],
            "deletedLeagueName": deleted["name"],
        }
    
    def update_owned_league_member(
        self, member_id: int, user_id: int, team_name: str,
    ) -> Dict[str, Any]:
        return MemberService(self.db).rename_for_owner_id(member_id, user_id, team_name)

    def update_league_member(self, member_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        # keep only allowed keys that are actually present
        return MemberService(self.db).update_for_job(member_id, updates)
