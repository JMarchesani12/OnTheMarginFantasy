"""Explicit global or authorized scoped league-local calendar transitions."""
from sqlalchemy import text, bindparam

LOCAL_TODAY = """(now() AT TIME ZONE COALESCE(
    NULLIF(l.settings #>> '{schedule,timezone}', ''),
    NULLIF(l.settings #>> '{schedule,timeZone}', ''),
    NULLIF(l.settings ->> 'timezone', ''),
    NULLIF(l.settings ->> 'timeZone', ''), 'UTC'
))::date"""


class LeagueLifecycleRepository:
    def mark_pre_draft(self, conn, league_ids=None, reader_user_id=None, members_only=False):
        self._execute(conn, f"""
                UPDATE "League" l
                SET status = 'Pre-Draft',
                    "updatedAt" = now()
                WHERE l.status NOT IN ('Pre-Draft', 'Completed')
                  AND NOT EXISTS (
                    SELECT 1
                    FROM "DraftState" ds
                    WHERE ds."leagueId" = l.id
                      AND ds.status IN ('live', 'paused', 'complete')
                  )
            """, league_ids, reader_user_id, members_only)

    def mark_drafting(self, conn, league_ids=None, reader_user_id=None, members_only=False):
        self._execute(conn, f"""
                UPDATE "League" l
                SET status = 'Drafting',
                    "updatedAt" = now()
                FROM "DraftState" ds
                WHERE ds."leagueId" = l.id
                  AND ds.status IN ('live', 'paused')
                  AND l.status <> 'Drafting'
            """, league_ids, reader_user_id, members_only)

    def mark_post_draft(self, conn, league_ids=None, reader_user_id=None, members_only=False):
        self._execute(conn, f"""
                UPDATE "League" l
                SET status = 'Post-Draft',
                    "updatedAt" = now()
                FROM "League" source
                JOIN "SportSeason" ss
                  ON ss."sportId" = source.sport
                 AND ss."seasonYear" = source."seasonYear"
                LEFT JOIN "DraftState" ds ON ds."leagueId" = source.id
                WHERE source.id = l.id
                  AND ds.status = 'complete'
                  AND {LOCAL_TODAY} < ss."seasonStart"::date
                  AND l.status <> 'Completed'
                  AND l.status <> 'Post-Draft'
            """, league_ids, reader_user_id, members_only)

    def mark_in_season(self, conn, league_ids=None, reader_user_id=None, members_only=False):
        self._execute(conn, f"""
                UPDATE "League" l
                SET status = 'In-Season',
                    "updatedAt" = now()
                FROM "SportSeason" ss
                WHERE ss."sportId" = l.sport
                  AND ss."seasonYear" = l."seasonYear"
                  AND {LOCAL_TODAY} >= ss."seasonStart"::date
                  AND {LOCAL_TODAY} <= ss."seasonEnd"::date
                  AND l.status NOT IN ('Drafting', 'In-Season', 'Completed')
                  AND EXISTS (
                    SELECT 1
                    FROM "DraftState" ds
                    WHERE ds."leagueId" = l.id
                      AND ds.status = 'complete'
                  )
            """, league_ids, reader_user_id, members_only)

    def mark_completed(self, conn, league_ids=None, reader_user_id=None, members_only=False):
        self._execute(conn, f"""
                UPDATE "League" l
                SET status = 'Completed',
                    "updatedAt" = now()
                FROM "SportSeason" ss
                WHERE ss."sportId" = l.sport
                  AND ss."seasonYear" = l."seasonYear"
                  AND {LOCAL_TODAY} > ss."seasonEnd"::date
                  AND l.status <> 'Completed'
            """, league_ids, reader_user_id, members_only)

    @staticmethod
    def _authorized_sql(members_only):
        membership = 'EXISTS (SELECT 1 FROM "LeagueMember" lm WHERE lm."leagueId"=l.id AND lm."userId"=:reader_id)'
        return membership if members_only else f'(l.commissioner=:reader_id OR {membership})'

    def _execute(self, conn, sql, league_ids, reader_user_id, members_only):
        if league_ids is None:
            if reader_user_id is not None or members_only:
                raise ValueError('Explicit league scope required')
            return conn.execute(text(sql))
        if isinstance(reader_user_id, bool) or not isinstance(reader_user_id, int):
            raise TypeError('A verified integer reader ID is required')
        if not league_ids:
            return None
        sql = sql.replace('WHERE ', f'WHERE l.id IN :scope_ids AND {self._authorized_sql(members_only)} AND ', 1)
        return conn.execute(text(sql).bindparams(bindparam('scope_ids', expanding=True)),
                            dict(scope_ids=list(league_ids),reader_id=reader_user_id))

    def candidate_ids(self, conn, user_id, league_id=None):
        predicate = self._authorized_sql(league_id is None)
        target = '' if league_id is None else 'AND l.id=:league_id'
        rows = conn.execute(text(f'SELECT l.id FROM "League" l WHERE {predicate} {target} ORDER BY l.id'),
                            dict(reader_id=user_id,league_id=league_id))
        return [int(row[0]) for row in rows]

    def lock_state(self, conn, league_id):
        return conn.execute(text('SELECT "leagueId" FROM "DraftState" WHERE "leagueId"=:id FOR UPDATE'),dict(id=league_id)).fetchone() is not None

    def lock_league(self, conn, league_id):
        return conn.execute(text('SELECT id FROM "League" WHERE id=:id FOR UPDATE'),dict(id=league_id)).fetchone() is not None

    def state_exists(self, conn, league_id):
        return conn.execute(text('SELECT "leagueId" FROM "DraftState" WHERE "leagueId"=:id'),dict(id=league_id)).fetchone() is not None

    def authorized(self, conn, league_id, user_id, members_only=False):
        return conn.execute(text(f'SELECT l.id FROM "League" l WHERE l.id=:id AND {self._authorized_sql(members_only)}'),
                            dict(id=league_id,reader_id=user_id)).fetchone() is not None
