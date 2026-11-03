"""Named workflow queries, scoped role SQL and shared entitlement query routing."""
from sqlalchemy import text
from utils.authorization import require_owned_league_member


class TransactionWorkflowRepository:
    def _trade_scope(self, role, params):
        role_scope = {
            'receiving': '"memberToId" = :member_id',
            'proposing': '"memberFromId" = :member_id',
            'voter': '"memberFromId" <> :member_id AND "memberToId" <> :member_id',
        }[role]
        return ' AND "leagueId" = :league_id AND ' + role_scope if 'league_id' in params else ''

    def league_settings(self, conn, params):
        return conn.execute(text('SELECT settings FROM "League" WHERE id = :league_id'), params)

    def member_swap_count(self, conn, params):
        return conn.execute(text(
            """
            SELECT COUNT(*) AS count
            FROM "Transaction"
            WHERE "leagueId" = :league_id
              AND "memberFromId" = :member_id
              AND type = :type
            """
        ), params)

    def member_count(self, conn, params):
        return conn.execute(text(
            """
            SELECT COUNT(*) AS count
            FROM "LeagueMember"
            WHERE "leagueId" = :league_id
              AND id = ANY(:member_ids)
            """
        ), params)

    def free_agent_deadline(self, conn, params):
        return conn.execute(text("""
                SELECT ("freeAgentDeadline" IS NOT NULL AND now() > "freeAgentDeadline") AS "pastDeadline"
                FROM "League"
                WHERE id = :league_id
            """), params)

    def week_for_league(self, conn, params):
        return conn.execute(text("""
            SELECT id, "weekNumber", "isLocked"
            FROM "Week"
            WHERE id = :week_id
            AND "leagueId" = :league_id
        """), params)

    def pending_add_ids(self, conn, params):
        return conn.execute(text("""
                SELECT DISTINCT (jsonb_array_elements_text(t."toTeamIds"))::int AS team_id
                FROM "Transaction" t
                WHERE t."leagueId" = :league_id
                  AND t."weekId" = :week_id
                  AND t.status = :status
                  AND t.type = :type
                  AND t."toTeamIds" IS NOT NULL
            """), params)

    def pending_drop_ids(self, conn, params):
        return conn.execute(text("""
                SELECT DISTINCT (jsonb_array_elements_text(t."fromTeamIds"))::int AS team_id
                FROM "Transaction" t
                WHERE t."leagueId" = :league_id
                  AND t."weekId" = :week_id
                  AND t.status = :status
                  AND t.type = :type
                  AND t."fromTeamIds" IS NOT NULL
            """), params)

    def free_agent_for_update(self, conn, params):
        return conn.execute(text("""
                    SELECT *
                    FROM "Transaction"
                    WHERE id = :id
                    FOR UPDATE
                """), params)

    def drop_free_agent_slots(self, conn, params):
        return conn.execute(text("""
                        UPDATE "LeagueTeamSlot"
                        SET "droppedWeek" = :week_number
                        WHERE "leagueId"   = :league_id
                          AND "memberId"   = :member_id
                          AND "sportTeamId" = ANY(:team_ids)
                          AND "acquiredWeek" <= :week_number
                          AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
                    """), params)

    def add_free_agent_slots(self, conn, params):
        return conn.execute(text("""
                    INSERT INTO "LeagueTeamSlot"
                        ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia")
                    VALUES
                        (:league_id, :member_id, :team_id, :week_number, :acquired_via)
                """), params)

    def complete_free_agent(self, conn, params):
        return conn.execute(text("""
                    UPDATE "Transaction"
                    SET status = :status
                    WHERE id = :id
                """), params)

    def pending_transaction(self, conn, params):
        return conn.execute(text("""
                    SELECT id, type, status
                    FROM "Transaction"
                    WHERE id = :id
                """), params)

    def next_unlocked_week(self, conn, params):
        return conn.execute(text("""
            SELECT id, "weekNumber", "isLocked"
            FROM "Week"
            WHERE "leagueId" = :league_id
              AND "weekNumber" > :week_number
              AND "isLocked" = FALSE
            ORDER BY "weekNumber" ASC
            LIMIT 1
        """), params)

    def insert_trade(self, conn, params):
        return conn.execute(text("""
                    INSERT INTO "Transaction"
                    ("leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds")
                    VALUES
                    (:league,:week,:type,:from_id,:to_id,:status, CAST(:from_teams AS jsonb), CAST(:to_teams AS jsonb))
                    RETURNING id
                """), params)

    def trade_for_action(self, conn, params, role):
        scope = self._trade_scope(role, params)
        return conn.execute(text('''
                SELECT * FROM "Transaction" WHERE id = :id
            ''' + scope + ' FOR UPDATE'), params)

    def trade_current_scope(self, conn, params, role):
        scope = self._trade_scope(role, params)
        return conn.execute(text(
                    'SELECT id FROM "Transaction" WHERE id = :id' + scope
                ), params)

    def reject_trade(self, conn, params):
        return conn.execute(text("""
                        UPDATE "Transaction"
                        SET status = :status,
                            "decidedByMemberId" = :by,
                            "rejectReason" = :reason
                        WHERE id = :id
                    """), params)

    def accept_trade(self, conn, params):
        return conn.execute(text("""
                    UPDATE "Transaction"
                    SET status = :status,
                        "decidedByMemberId" = :by
                    WHERE id = :id
                """), params)

    def cancel_trade(self, conn, params):
        return conn.execute(text("""
                    UPDATE "Transaction"
                    SET status = :status,
                        "decidedByMemberId" = :by
                    WHERE id = :id
                """), params)

    def team_owned(self, conn, params):
        return conn.execute(text("""
            SELECT 1
            FROM "LeagueTeamSlot"
            WHERE "leagueId" = :league_id
            AND "sportTeamId" = :team_id
            AND "acquiredWeek" <= :week_number
            AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
            LIMIT 1
        """), params)

    def member_team_owned(self, conn, params):
        return conn.execute(text("""
            SELECT 1
            FROM "LeagueTeamSlot"
            WHERE "leagueId" = :league_id
            AND "memberId" = :member_id
            AND "sportTeamId" = :team_id
            AND "acquiredWeek" <= :week_number
            AND ("droppedWeek" IS NULL OR "droppedWeek" > :week_number)
            LIMIT 1
        """), params)

    def team_conference_info(self, conn, params):
        return conn.execute(text("""
                SELECT
                cm."sportTeamId"       AS "sportTeamId",
                cm."sportConferenceId" AS "sportConferenceId",
                sc."maxTeamsPerOwner"  AS "maxTeamsPerOwner"
                FROM "ConferenceMembership" cm
                JOIN "SportConference" sc
                ON sc.id = cm."sportConferenceId"
                WHERE cm."sportTeamId" = ANY(:team_ids)
            """), params)

    def member_conference_counts(self, conn, params):
        return conn.execute(text("""
                SELECT
                cm."sportConferenceId" AS "sportConferenceId",
                COUNT(*)              AS "cnt"
                FROM "LeagueTeamSlot" lts
                JOIN "ConferenceMembership" cm
                ON cm."sportTeamId" = lts."sportTeamId"
                WHERE lts."leagueId" = :league_id
                AND lts."memberId" = :member_id
                AND lts."acquiredWeek" <= :week_number
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week_number)
                GROUP BY cm."sportConferenceId"
            """), params)

    def member_roster_ids(self, conn, params):
        return conn.execute(text("""
                SELECT lts."sportTeamId" AS "sportTeamId"
                FROM "LeagueTeamSlot" lts
                WHERE lts."leagueId" = :league_id
                AND lts."memberId" = :member_id
                AND lts."acquiredWeek" <= :week_number
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week_number)
                ORDER BY lts."sportTeamId"
            """), params)

    def insert_free_agent(self, conn, params):
        return conn.execute(text(
                """
                INSERT INTO "Transaction"
                    ("leagueId", "weekId", type, "memberFromId", "memberToId", status, "fromTeamIds", "toTeamIds")
                VALUES
                    (:league_id, :week_id, :type, :member_from_id, :member_to_id, :status, CAST(:from_teams AS jsonb), CAST(:to_teams AS jsonb))
                RETURNING id
                """
            ), params)

    def roster_violations(self, conn, params):
        return conn.execute(text(
            """
            SELECT
              lts."memberId"           AS "memberId",
              cm."sportConferenceId"   AS "sportConferenceId",
              sc."maxTeamsPerOwner"    AS "maxTeamsPerOwner",
              COUNT(*)                 AS "count"
            FROM "LeagueTeamSlot" lts
            JOIN "ConferenceMembership" cm
              ON cm."sportTeamId" = lts."sportTeamId"
            JOIN "SportConference" sc
              ON sc.id = cm."sportConferenceId"
            WHERE lts."leagueId" = :league_id
              AND lts."acquiredWeek" <= :week_number
              AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week_number)
            GROUP BY
              lts."memberId",
              cm."sportConferenceId",
              sc."maxTeamsPerOwner"
            HAVING COUNT(*) > sc."maxTeamsPerOwner"
            """
        ), params)

    def open_trades(self, conn, params):
        scope = '''AND EXISTS (
                SELECT 1 FROM "LeagueMember" reader_member
                JOIN "League" reader_league ON reader_league.id = reader_member."leagueId"
                WHERE reader_member.id = :member_id
                  AND reader_member."leagueId" = :league_id
                  AND reader_member."userId" = :reader_user_id
            )''' if 'reader_user_id' in params else ''
        return conn.execute(text("""
            SELECT
            t.id,
            t."leagueId",
            t."weekId",
            t.type,
            t.status,
            t."memberFromId",
            t."memberToId",
            t."createdAt",

            -- member context
            COALESCE(tv_me.veto, false) AS "memberHasVetoed",
            (t."memberFromId" = :member_id OR t."memberToId" = :member_id) AS "isParticipant",

            -- counts for UI
            (
                SELECT COUNT(*)
                FROM "TransactionVote" tvc
                WHERE tvc."transactionId" = t.id
                AND tvc.veto = true
            ) AS "vetoCount",

            -- member display info
            lm_from."teamName" AS "memberFromTeamName",
            u_from."displayName" AS "memberFromDisplayName",
            lm_to."teamName" AS "memberToTeamName",
            u_to."displayName" AS "memberToDisplayName",

            -- FROM teams
            COALESCE(
                jsonb_agg(
                DISTINCT jsonb_build_object(
                    'id', st_from.id,
                    'displayName', st_from."displayName"
                )
                ) FILTER (WHERE st_from.id IS NOT NULL),
                '[]'::jsonb
            ) AS "fromTeams",

            -- TO teams
            COALESCE(
                jsonb_agg(
                DISTINCT jsonb_build_object(
                    'id', st_to.id,
                    'displayName', st_to."displayName"
                )
                ) FILTER (WHERE st_to.id IS NOT NULL),
                '[]'::jsonb
            ) AS "toTeams"

            FROM "Transaction" t

            -- requesting member's veto (at most 1 row due to unique constraint)
            LEFT JOIN "TransactionVote" tv_me
            ON tv_me."transactionId" = t.id
            AND tv_me."leagueMemberId" = :member_id

            LEFT JOIN "LeagueMember" lm_from
            ON lm_from.id = t."memberFromId"
            LEFT JOIN "User" u_from
            ON u_from.id = lm_from."userId"

            LEFT JOIN "LeagueMember" lm_to
            ON lm_to.id = t."memberToId"
            LEFT JOIN "User" u_to
            ON u_to.id = lm_to."userId"

            -- Expand FROM team ids
            LEFT JOIN LATERAL jsonb_array_elements_text(t."fromTeamIds") AS f(team_id)
            ON TRUE
            LEFT JOIN "SportTeam" st_from
            ON st_from.id = f.team_id::bigint

            -- Expand TO team ids
            LEFT JOIN LATERAL jsonb_array_elements_text(t."toTeamIds") AS tt(team_id)
            ON TRUE
            LEFT JOIN "SportTeam" st_to
            ON st_to.id = tt.team_id::bigint

            WHERE t."leagueId" = :league_id
            AND t.type = 'TRADE'
            AND t.status NOT IN ('COMPLETED', 'REJECTED', 'CANCELLED', 'VETOED')

            """ + scope + """
            GROUP BY
            t.id,
            t."leagueId",
            t."weekId",
            t.type,
            t.status,
            t."memberFromId",
            t."memberToId",
            t."createdAt",
            tv_me.veto,
            lm_from."teamName",
            u_from."displayName",
            lm_to."teamName",
            u_to."displayName",
            (t."memberFromId" = :member_id OR t."memberToId" = :member_id)

            ORDER BY t."createdAt" DESC
        """), params)

    def toggle_veto(self, conn, params):
        return conn.execute(text("""
                    UPDATE "TransactionVote"
                    SET veto = NOT veto
                    WHERE "transactionId" = :tx_id
                    AND "leagueMemberId" = :lm_id
                    RETURNING veto
                """), params)

    def insert_veto(self, conn, params):
        return conn.execute(text("""
                        INSERT INTO "TransactionVote"
                            ("transactionId","leagueMemberId",veto)
                        VALUES
                            (:tx_id, :lm_id, true)
                        RETURNING veto
                    """), params)

    def veto_count(self, conn, params):
        return conn.execute(text("""
                    SELECT COUNT(*) AS cnt
                    FROM "TransactionVote"
                    WHERE "transactionId" = :tx_id
                    AND veto = true
                """), params)

    def mark_vetoed(self, conn, params):
        return conn.execute(text("""
                        UPDATE "Transaction"
                        SET status = :status
                        WHERE id = :id
                    """), params)

    def assert_owned_member(self, conn, league_id, member_id, user_id):
        return require_owned_league_member(conn, league_id, member_id, user_id)

    def lock_week(self, conn, params):
        return conn.execute(text(
            """
            UPDATE "Week"
            SET "isLocked" = true
            WHERE id = :week_id
              AND "leagueId" = :league_id
            """
        ), params)
