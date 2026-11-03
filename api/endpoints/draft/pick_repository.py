"""Named draft pick/timeout queries; transaction and result consumption belong to caller."""
from sqlalchemy import text
from .notifyChannel import notify_draft_updated


class DraftPickRepository:

    def membership_for_subject(self, conn, params):
        return conn.execute(text("""
            SELECT 1
            FROM "LeagueMember" lm
            JOIN "User" u ON u.id = lm."userId"
            WHERE lm."leagueId" = :leagueId
              AND u.uuid = CAST(:uuid AS uuid)
            LIMIT 1
        """), params)

    def member_for_order(self, conn, params):
        return conn.execute(text("""
                SELECT id
                FROM "LeagueMember"
                WHERE "leagueId" = :leagueId AND "draftOrder" = :draftOrder
                LIMIT 1
            """), params)

    def live_owned_member(self, conn, params):
        ownership_scope = 'WHERE EXISTS (\n                SELECT 1 FROM "LeagueMember" owned_member\n                WHERE owned_member.id = :memberId\n                  AND owned_member."leagueId" = :leagueId\n                  AND owned_member."userId" = :actingUserId\n            )' if 'actingUserId' in params else ''
        return conn.execute(text(f'SELECT 1 {ownership_scope}'), params)

    def live_state_for_update(self, conn, params):
        return conn.execute(text("""
                    SELECT "leagueId", status, "currentOverallPickNumber", "currentMemberId", "expiresAt"
                    FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                    FOR UPDATE
                """), params)

    def live_team_ownership(self, conn, params):
        return conn.execute(text("""
                    SELECT 1
                    FROM "LeagueTeamSlot"
                    WHERE "leagueId" = :leagueId
                      AND "sportTeamId" = :sportTeamId
                      AND "acquiredWeek" <= :week
                      AND ("droppedWeek" IS NULL OR "droppedWeek" > :week)
                    LIMIT 1
                """), params)

    def insert_live_pick(self, conn, params):
        ownership_scope = 'WHERE EXISTS (\n                SELECT 1 FROM "LeagueMember" owned_member\n                WHERE owned_member.id = :memberId\n                  AND owned_member."leagueId" = :leagueId\n                  AND owned_member."userId" = :actingUserId\n            )' if 'actingUserId' in params else ''
        return conn.execute(text(f"""
                        INSERT INTO "DraftPick"
                            ("leagueId", "overallPickNumber", "roundNumber", "pickInRound",
                             "memberId", "sportTeamId")
                        SELECT :leagueId, :overallPickNumber, :roundNumber, :pickInRound,
                               :memberId, :sportTeamId
                        {ownership_scope}
                        RETURNING id, "createdAt", "leagueId",
                                  "overallPickNumber", "roundNumber", "pickInRound",
                                  "memberId", "sportTeamId"
                    """), params)

    def insert_live_slot(self, conn, params):
        return conn.execute(text("""
                    INSERT INTO "LeagueTeamSlot"
                        ("leagueId", "memberId", "sportTeamId",
                         "acquiredWeek", "acquiredVia")
                    VALUES
                        (:leagueId, :memberId, :sportTeamId,
                         :acquiredWeek, :acquiredVia)
                    RETURNING id
                """), params)

    def live_advance_past_end(self, conn, params):
        return conn.execute(text("""
                        UPDATE "DraftState"
                        SET "currentOverallPickNumber" = :nextOverall,
                            "updatedAt" = now()
                        WHERE "leagueId" = :leagueId
                    """), params)

    def live_advance_without_turn(self, conn, params):
        return conn.execute(text("""
                        UPDATE "DraftState"
                        SET "currentOverallPickNumber" = :nextOverall,
                            "updatedAt" = now()
                        WHERE "leagueId" = :leagueId
                    """), params)

    def live_advance_next(self, conn, params):
        return conn.execute(text("""
                    UPDATE "DraftState"
                    SET "currentOverallPickNumber" = :nextOverall,
                        "currentMemberId" = :nextMemberId,
                        "expiresAt" = now() + (:selectionTime || ' seconds')::interval,
                        "lastPickAt" = now(),
                        "updatedAt" = now()
                    WHERE "leagueId" = :leagueId
                """), params)

    def timeout_state_for_update(self, conn, params):
        return conn.execute(text("""
                    SELECT "leagueId", status, "currentOverallPickNumber", "currentMemberId", "expiresAt"
                    FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                    FOR UPDATE
                """), params)

    def timeout_expired(self, conn, params):
        return conn.execute(text("""
                    SELECT now() > ("expiresAt" + (:graceSeconds || ' seconds')::interval) AS "isExpired"
                    FROM "DraftState"
                    WHERE "leagueId" = :leagueId
                """), params)

    def timeout_expected_member(self, conn, params):
        return conn.execute(text("""
                        SELECT "memberId"
                        FROM "DraftTurn"
                        WHERE "leagueId" = :leagueId
                          AND "overallPickNumber" = :overall
                    """), params)

    def timeout_last_unpicked(self, conn, params):
        return conn.execute(text("""
                        SELECT COALESCE(MAX(dt."overallPickNumber"), 0) AS "lastUnpicked"
                        FROM "DraftTurn" dt
                        LEFT JOIN "DraftPick" dp
                          ON dp."leagueId" = dt."leagueId"
                         AND dp."overallPickNumber" = dt."overallPickNumber"
                        WHERE dt."leagueId" = :leagueId
                          AND dp.id IS NULL
                    """), params)

    def timeout_extend_clock(self, conn, params):
        return conn.execute(text("""
                            UPDATE "DraftState"
                            SET "expiresAt" = now() + (:selectionTime || ' seconds')::interval,
                                "updatedAt" = now()
                            WHERE "leagueId" = :leagueId
                        """), params)

    def timeout_rotate_turns(self, conn, params):
        return conn.execute(text("""
                        WITH params AS (
                            SELECT
                                CAST(:leagueId AS bigint) AS "leagueId",
                                CAST(:cur AS bigint)      AS "cur",
                                CAST(:last AS bigint)     AS "last"
                        ),
                        unpicked AS (
                            SELECT dt."overallPickNumber" AS "opn",
                                   dt."memberId"          AS "memberId"
                            FROM "DraftTurn" dt
                            JOIN params p ON p."leagueId" = dt."leagueId"
                            LEFT JOIN "DraftPick" dp
                              ON dp."leagueId" = dt."leagueId"
                             AND dp."overallPickNumber" = dt."overallPickNumber"
                            WHERE dt."overallPickNumber" BETWEEN p."cur" AND p."last"
                              AND dp.id IS NULL
                            ORDER BY dt."overallPickNumber"
                        ),
                        saved AS (
                            SELECT u."memberId" AS "savedMemberId"
                            FROM unpicked u
                            WHERE u."opn" = (SELECT "cur" FROM params)
                        ),
                        shifted AS (
                            SELECT
                                u."opn" AS "opn",
                                LEAD(u."memberId") OVER (ORDER BY u."opn") AS "nextMemberId"
                            FROM unpicked u
                        )
                        UPDATE "DraftTurn" dt
                        SET "memberId" = COALESCE(
                            (SELECT s."nextMemberId" FROM shifted s WHERE s."opn" = dt."overallPickNumber"),
                            (SELECT "savedMemberId" FROM saved)
                        )
                        WHERE dt."leagueId" = (SELECT "leagueId" FROM params)
                          AND dt."overallPickNumber" IN (SELECT "opn" FROM shifted);
                    """), params)

    def timeout_next_turn(self, conn, params):
        return conn.execute(text("""
                        SELECT dt."overallPickNumber" AS "nextOverall",
                               dt."memberId"          AS "nextMemberId"
                        FROM "DraftTurn" dt
                        LEFT JOIN "DraftPick" dp
                          ON dp."leagueId" = dt."leagueId"
                         AND dp."overallPickNumber" = dt."overallPickNumber"
                        WHERE dt."leagueId" = :leagueId
                          AND dp.id IS NULL
                          AND dt."overallPickNumber" >= :cur
                        ORDER BY dt."overallPickNumber" ASC
                        LIMIT 1
                    """), params)

    def timeout_advance(self, conn, params):
        return conn.execute(text("""
                        UPDATE "DraftState"
                        SET "currentOverallPickNumber" = :nextOverall,
                            "currentMemberId" = :nextMemberId,
                            "expiresAt" = now() + (:selectionTime || ' seconds')::interval,
                            "lastPickAt" = now(),
                            "updatedAt" = now()
                        WHERE "leagueId" = :leagueId
                    """), params)

    def timeout_auto_member(self, conn, params):
        return conn.execute(text("""
                        SELECT dt."memberId"
                        FROM "DraftTurn" dt
                        WHERE dt."leagueId" = :leagueId
                          AND dt."overallPickNumber" = :overall
                    """), params)

    def conference_info(self, conn, params):
        return conn.execute(text("""
            WITH league_info AS (
              SELECT "seasonYear"
              FROM "League"
              WHERE id = :leagueId
            )
            SELECT
              sc.id                 AS "sportConferenceId",
              c.name                AS "conferenceName",
              sc."maxTeamsPerOwner" AS "maxTeamsPerOwner"
            FROM "SportTeam" st
            JOIN "ConferenceMembership" cm
              ON cm."sportTeamId" = st.id
             AND cm."sportId" = st."sportId"
            CROSS JOIN league_info li
            JOIN "SportConference" sc
              ON sc.id = cm."sportConferenceId"
             AND sc."sportId" = st."sportId"
            JOIN "Conference" c
              ON c.id = sc."conferenceId"
            WHERE st.id = :sportTeamId
              AND (cm."seasonYear" IS NULL OR cm."seasonYear" = li."seasonYear")
            LIMIT 1
        """), params)

    def member_conference_count(self, conn, params):
        return conn.execute(text("""
            WITH league_info AS (
              SELECT "seasonYear"
              FROM "League"
              WHERE id = :leagueId
            ),
            owned AS (
              SELECT lts."sportTeamId"
              FROM "LeagueTeamSlot" lts
              WHERE lts."leagueId"     = :leagueId
                AND lts."memberId"     = :memberId
                AND lts."acquiredWeek" <= :weekNumber
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
            )
            SELECT COUNT(DISTINCT o."sportTeamId")::int AS cnt
            FROM owned o
            JOIN "SportTeam" st
              ON st.id = o."sportTeamId"
            JOIN "ConferenceMembership" cm
              ON cm."sportTeamId" = st.id
             AND cm."sportId" = st."sportId"
            CROSS JOIN league_info li
            JOIN "SportConference" sc
              ON sc.id = cm."sportConferenceId"
             AND sc."sportId" = st."sportId"
            WHERE sc.id = :sportConferenceId
              AND (cm."seasonYear" IS NULL OR cm."seasonYear" = li."seasonYear")
        """), params)

    def manual_league(self, conn, params):
        return conn.execute(text('SELECT "numPlayers" FROM "League" WHERE id = :leagueId'), params)

    def manual_team_ownership(self, conn, params):
        return conn.execute(text("""
                    SELECT 1
                    FROM "LeagueTeamSlot"
                    WHERE "leagueId" = :leagueId
                      AND "sportTeamId" = :sportTeamId
                      AND "acquiredWeek" <= :week
                      AND ("droppedWeek" IS NULL OR "droppedWeek" > :week)
                    LIMIT 1
                """), params)

    def manual_pick_count(self, conn, params):
        return conn.execute(text('SELECT COUNT(*) AS cnt FROM "DraftPick" WHERE "leagueId" = :leagueId'), params)

    def insert_manual_pick(self, conn, params):
        return conn.execute(text("""
                INSERT INTO "DraftPick"
                    ("leagueId", "overallPickNumber", "roundNumber", "pickInRound",
                     "memberId", "sportTeamId")
                VALUES
                    (:leagueId, :overallPickNumber, :roundNumber, :pickInRound,
                     :memberId, :sportTeamId)
                RETURNING id, "createdAt", "leagueId",
                          "overallPickNumber", "roundNumber", "pickInRound",
                          "memberId", "sportTeamId"
            """), params)

    def insert_manual_slot(self, conn, params):
        return conn.execute(text("""
                INSERT INTO "LeagueTeamSlot"
                    ("leagueId", "memberId", "sportTeamId",
                     "acquiredWeek", "acquiredVia")
                VALUES
                    (:leagueId, :memberId, :sportTeamId,
                     :acquiredWeek, :acquiredVia)
                RETURNING id
            """), params)

    def sport_rounds(self, conn, params):
        return conn.execute(text('SELECT "maxDraftRounds" FROM "Sport" WHERE id = :sportId'), params)

    def league_sport(self, conn, params):
        return conn.execute(text("""SELECT sport FROM "League" WHERE id = :leagueId"""), params)

    def sport_conference_ids(self, conn, params):
        return conn.execute(text("""
                SELECT id
                FROM "SportConference"
                WHERE "sportId" = :sportId
                ORDER BY id ASC
            """), params)

    def owned_conference_count(self, conn, params):
        return conn.execute(text("""
                WITH league_info AS (
                  SELECT "seasonYear"
                  FROM "League"
                  WHERE id = :leagueId
                )
                SELECT COUNT(*) AS cnt
                FROM "LeagueTeamSlot" lts
                JOIN "SportTeam" st
                ON st.id = lts."sportTeamId"
                JOIN "ConferenceMembership" cm
                ON cm."sportTeamId" = st.id
                AND cm."sportId" = st."sportId"
                CROSS JOIN league_info li
                JOIN "SportConference" sc
                ON sc.id = cm."sportConferenceId"
                AND sc."sportId" = st."sportId"
                WHERE lts."leagueId" = :leagueId
                AND lts."memberId" = :memberId
                AND lts."acquiredWeek" <= :week
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week)
                AND sc.id = :sportConferenceId
                AND (cm."seasonYear" IS NULL OR cm."seasonYear" = li."seasonYear")
            """), params)

    def conference_cap(self, conn, params):
        return conn.execute(text("""
                SELECT "maxTeamsPerOwner"
                FROM "SportConference"
                WHERE id = :sportConferenceId
            """), params)

    def random_conference_team(self, conn, params):
        return conn.execute(text("""
                WITH league_info AS (
                  SELECT "seasonYear"
                  FROM "League"
                  WHERE id = :leagueId
                )
                SELECT st.id AS "sportTeamId"
                FROM "ConferenceMembership" cm
                CROSS JOIN league_info li
                JOIN "SportTeam" st
                ON st.id = cm."sportTeamId"
                AND st."sportId" = cm."sportId"
                JOIN "SportConference" sc
                ON sc.id = cm."sportConferenceId"
                AND sc."sportId" = st."sportId"
                LEFT JOIN "DraftPick" dp
                ON dp."leagueId" = :leagueId
                AND dp."sportTeamId" = st.id
                LEFT JOIN "LeagueTeamSlot" lts
                ON lts."leagueId" = :leagueId
                AND lts."sportTeamId" = st.id
                AND lts."acquiredWeek" <= :week
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week)
                WHERE sc.id = :sportConferenceId
                AND (cm."seasonYear" IS NULL OR cm."seasonYear" = li."seasonYear")
                AND dp.id IS NULL
                AND lts.id IS NULL
                ORDER BY random()
                LIMIT 1
            """), params)

    def random_independent_team(self, conn, params):
        return conn.execute(text("""
                WITH league_info AS (
                  SELECT "seasonYear"
                  FROM "League"
                  WHERE id = :leagueId
                )
                SELECT st.id AS "sportTeamId"
                FROM "SportTeam" st
                CROSS JOIN league_info li
                LEFT JOIN "DraftPick" dp
                ON dp."leagueId" = :leagueId
                AND dp."sportTeamId" = st.id
                LEFT JOIN "LeagueTeamSlot" lts
                ON lts."leagueId" = :leagueId
                AND lts."sportTeamId" = st.id
                AND lts."acquiredWeek" <= :week
                AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week)
                WHERE st."sportId" = :sportId
                AND NOT EXISTS (
                  SELECT 1
                  FROM "ConferenceMembership" cm
                  WHERE cm."sportTeamId" = st.id
                    AND cm."sportId" = st."sportId"
                    AND (cm."seasonYear" IS NULL OR cm."seasonYear" = li."seasonYear")
                )
                AND dp.id IS NULL
                AND lts.id IS NULL
                ORDER BY random()
                LIMIT 1
            """), params)

    def auto_state_for_update(self, conn, params):
        return conn.execute(text("""
                SELECT status, "currentOverallPickNumber"
                FROM "DraftState"
                WHERE "leagueId" = :leagueId
                FOR UPDATE
            """), params)

    def insert_auto_pick(self, conn, params):
        return conn.execute(text("""
                    INSERT INTO "DraftPick"
                        ("leagueId", "overallPickNumber", "roundNumber", "pickInRound",
                        "memberId", "sportTeamId")
                    VALUES
                        (:leagueId, :overallPickNumber, :roundNumber, :pickInRound,
                        :memberId, :sportTeamId)
                    RETURNING id, "createdAt", "leagueId",
                            "overallPickNumber", "roundNumber", "pickInRound",
                            "memberId", "sportTeamId"
                """), params)

    def insert_auto_slot(self, conn, params):
        return conn.execute(text("""
                INSERT INTO "LeagueTeamSlot"
                    ("leagueId", "memberId", "sportTeamId",
                    "acquiredWeek", "acquiredVia")
                VALUES
                    (:leagueId, :memberId, :sportTeamId,
                    :acquiredWeek, :acquiredVia)
                RETURNING id
            """), params)

    def auto_advance_past_end(self, conn, params):
        return conn.execute(text("""
                    UPDATE "DraftState"
                    SET "currentOverallPickNumber" = :nextOverall,
                        "updatedAt" = now()
                    WHERE "leagueId" = :leagueId
                """), params)

    def auto_advance_next(self, conn, params):
        return conn.execute(text("""
                UPDATE "DraftState"
                SET "currentOverallPickNumber" = :nextOverall,
                    "currentMemberId" = :nextMemberId,
                    "expiresAt" = now() + (:selectionTime || ' seconds')::interval,
                    "lastPickAt" = now(),
                    "updatedAt" = now()
                WHERE "leagueId" = :leagueId
            """), params)

    def notify(self, conn, league_id, reason):
        notify_draft_updated(conn, league_id, reason)

    def next_timeout_deadline(self, conn):
        return conn.execute(text("""
            SELECT
                ds."leagueId" AS "leagueId",
                EXTRACT(EPOCH FROM (
                    (ds."expiresAt" + ((l.settings->'draft'->>'graceSeconds') || ' seconds')::interval)
                    - now()
                )) AS "secondsUntilDeadline"
            FROM "DraftState" ds
            JOIN "League" l ON l.id = ds."leagueId"
            WHERE ds.status = 'live'
              AND ds."expiresAt" IS NOT NULL
            ORDER BY (ds."expiresAt" + ((l.settings->'draft'->>'graceSeconds') || ' seconds')::interval) ASC
            LIMIT 1
        """))
