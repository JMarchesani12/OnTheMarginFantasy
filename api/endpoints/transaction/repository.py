"""Transaction persistence. Connections come from the calling service."""
from typing import Any, Dict, List
from sqlalchemy import text
from utils.authorization import league_read_scope


class TransactionRepository:
    def league_read_allowed(self, conn, league_id, user_id):
        scope, params = league_read_scope(league_id, user_id)
        return conn.execute(text('SELECT id FROM "League" WHERE id = :leagueId ' + scope),
                            {'leagueId': league_id, **params}).fetchone() is not None

    def lock_trade(self, conn, transaction_id):
        row = conn.execute(text('SELECT * FROM "Transaction" WHERE id = :id FOR UPDATE'),
                           {'id': transaction_id}).fetchone()
        return dict(row._mapping) if row else None

    def past_trade_deadline(self, conn, league_id):
        row = conn.execute(text('''SELECT ("tradeDeadline" IS NOT NULL AND now() > "tradeDeadline") AS "pastDeadline"
            FROM "League" WHERE id = :league_id'''), {'league_id': league_id}).fetchone()
        return bool(row._mapping['pastDeadline']) if row else None

    def trade_week(self, conn, league_id, week_id):
        row = conn.execute(text('SELECT "weekNumber" FROM "Week" WHERE id = :week_id AND "leagueId" = :league_id'),
                           {'week_id': week_id, 'league_id': league_id}).fetchone()
        return dict(row._mapping) if row else None

    def mark_trade_completed(self, conn, transaction_id):
        conn.execute(text('''UPDATE "Transaction" SET status = :status WHERE id = :id'''),
                     {'status': 'COMPLETED', 'id': transaction_id})

    def list_transactions(self, conn, league_id, status=None, reader_user_id=None):
        scope, reader_params = league_read_scope(league_id, reader_user_id)
        sql = """
            SELECT
              t.id,
              t."leagueId",
              t."weekId",
              w."weekNumber",
              t.type,
              t.status,
              t."memberFromId",
              t."memberToId",
              u_from."displayName" AS "memberFromDisplayName",
              u_to."displayName" AS "memberToDisplayName",
              ft."fromTeams",
              tt."toTeams",
              t."createdAt"
            FROM "Transaction" t
            LEFT JOIN "Week" w ON w.id = t."weekId"
            LEFT JOIN "LeagueMember" lm_from ON lm_from.id = t."memberFromId"
            LEFT JOIN "User" u_from ON u_from.id = lm_from."userId"
            LEFT JOIN "LeagueMember" lm_to ON lm_to.id = t."memberToId"
            LEFT JOIN "User" u_to ON u_to.id = lm_to."userId"
            LEFT JOIN LATERAL (
              SELECT jsonb_agg(
                jsonb_build_object(
                  'id', st.id,
                  'displayName', st."displayName"
                )
                ORDER BY st."displayName"
              ) AS "fromTeams"
              FROM jsonb_array_elements_text(t."fromTeamIds") AS f(team_id)
              JOIN "SportTeam" st ON st.id = (f.team_id)::int
            ) ft ON TRUE
            LEFT JOIN LATERAL (
              SELECT jsonb_agg(
                jsonb_build_object(
                  'id', st.id,
                  'displayName', st."displayName"
                )
                ORDER BY st."displayName"
              ) AS "toTeams"
              FROM jsonb_array_elements_text(t."toTeamIds") AS tt(team_id)
              JOIN "SportTeam" st ON st.id = (tt.team_id)::int
            ) tt ON TRUE
            WHERE t."leagueId" = :leagueId
        """
        sql += scope
        params: Dict[str, Any] = {"leagueId": league_id, **reader_params}
        if status:
            sql += " AND t.status = :status"
            params["status"] = status

        sql += ' ORDER BY t."createdAt" DESC, t.id DESC'

        rows = conn.execute(text(sql), params).mappings().all()

        return [dict(r) for r in rows]

    def trade_ownership(self, conn, league_id, week_number, from_team_ids, to_team_ids):
        ownership_rows = conn.execute(
            text("""
                SELECT "sportTeamId","memberId"
                FROM "LeagueTeamSlot"
                WHERE "leagueId" = :league_id
                AND "sportTeamId" = ANY(:team_ids)
                AND "acquiredWeek" <= :week_number
                AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
            """),
            {
                "league_id": league_id,
                "week_number": week_number,
                "team_ids": from_team_ids + to_team_ids,
            },
        ).fetchall()
        return {r._mapping["sportTeamId"]: r._mapping["memberId"] for r in ownership_rows}

    def conference_counts(self, conn, league_id, week_number, member_id: int, exclude_ids: List[int]) -> Dict[int, int]:
        rows = conn.execute(
            text("""
                SELECT cm."sportConferenceId", COUNT(*) AS cnt
                FROM "LeagueTeamSlot" lts
                JOIN "ConferenceMembership" cm
                ON cm."sportTeamId" = lts."sportTeamId"
                WHERE lts."leagueId" = :league_id
                AND lts."memberId" = :member_id
                AND lts."acquiredWeek" <= :week_number
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week_number)
                AND NOT (lts."sportTeamId" = ANY(:exclude_ids))
                GROUP BY cm."sportConferenceId"
            """),
            {
                "league_id": league_id,
                "week_number": week_number,
                "member_id": member_id,
                "exclude_ids": exclude_ids,
            },
        ).fetchall()


        return {r._mapping["sportConferenceId"]: r._mapping["cnt"] for r in rows}

    def incoming_confs(self, conn, team_ids: List[int]) -> Dict[int, int]:
        rows = conn.execute(
            text("""
                SELECT "sportConferenceId", COUNT(*) AS cnt
                FROM "ConferenceMembership"
                WHERE "sportTeamId" = ANY(:team_ids)
                GROUP BY "sportConferenceId"
            """),
            {"team_ids": team_ids},
        ).fetchall()
        return {r._mapping["sportConferenceId"]: r._mapping["cnt"] for r in rows}

    def conference_limits(self, conn):
        limit_rows = conn.execute(
            text("""
                SELECT id, "maxTeamsPerOwner"
                FROM "SportConference"
            """)
        ).fetchall()
        return {r._mapping["id"]: r._mapping["maxTeamsPerOwner"] for r in limit_rows}

    def transfer_ownership(
        self,
        conn,
        league_id: int,
        week_number: int,
        from_member_id: int,
        to_member_id: int,
        from_team_ids: List[int],
        to_team_ids: List[int],
    ) -> None:
        # 1) Close out current ownership rows for teams leaving each member
        if from_team_ids:
            conn.execute(
                text("""
                    UPDATE "LeagueTeamSlot"
                    SET "droppedWeek" = :week_number
                    WHERE "leagueId" = :league_id
                    AND "memberId" = :member_id
                    AND "sportTeamId" = ANY(:team_ids)
                    AND "acquiredWeek" <= :week_number
                    AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
                """),
                {
                    "league_id": league_id,
                    "member_id": from_member_id,
                    "team_ids": from_team_ids,
                    "week_number": week_number,
                },
            )

        if to_team_ids:
            conn.execute(
                text("""
                    UPDATE "LeagueTeamSlot"
                    SET "droppedWeek" = :week_number
                    WHERE "leagueId" = :league_id
                    AND "memberId" = :member_id
                    AND "sportTeamId" = ANY(:team_ids)
                    AND "acquiredWeek" <= :week_number
                    AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
                """),
                {
                    "league_id": league_id,
                    "member_id": to_member_id,
                    "team_ids": to_team_ids,
                    "week_number": week_number,
                },
            )

        # 2) Insert new ownership rows starting this week (executemany)
        insert_sql = text("""
            INSERT INTO "LeagueTeamSlot"
                ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia")
            VALUES
                (:league_id, :member_id, :team_id, :week_number, :acquired_via)
        """)

        if from_team_ids:
            rows = [
                {
                    "league_id": league_id,
                    "member_id": to_member_id,
                    "team_id": int(tid),
                    "week_number": week_number,
                    "acquired_via": 'TRADE',
                }
                for tid in from_team_ids
            ]
            conn.execute(insert_sql, rows)

        if to_team_ids:
            rows = [
                {
                    "league_id": league_id,
                    "member_id": from_member_id,
                    "team_id": int(tid),
                    "week_number": week_number,
                    "acquired_via": 'TRADE',
                }
                for tid in to_team_ids
            ]
            conn.execute(insert_sql, rows)

