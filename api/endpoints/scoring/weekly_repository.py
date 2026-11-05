"""Weekly job progress SQL. Caller supplies connection and ownership mutex."""
from sqlalchemy import text


class WeeklyCompletionRepository:
    def candidates(self, conn, now):
        rows=conn.execute(text('''
            SELECT "leagueId" FROM "Week"
            WHERE "endDate" < :now AND "weekNumber">=0 AND "scoringComplete"=false
            UNION
            SELECT "leagueId" FROM "Transaction" WHERE status='PENDING_APPLY'
            ORDER BY "leagueId"
        '''), {'now':now}).fetchall()
        return [int(row._mapping['leagueId']) for row in rows]

    def periods(self, conn, league_id, now):
        return [dict(row._mapping) for row in conn.execute(text('''
            SELECT id,"weekNumber","scoringComplete",("endDate" < :now) AS ended
            FROM "Week" WHERE "leagueId"=:leagueId AND "weekNumber">=0
            ORDER BY "weekNumber" FOR UPDATE
        '''), {'leagueId':league_id,'now':now}).fetchall()]

    def pending(self, conn, league_id):
        return [dict(row._mapping) for row in conn.execute(text('''
            SELECT id,"weekId" FROM "Transaction"
            WHERE "leagueId"=:leagueId AND status='PENDING_APPLY'
            ORDER BY id FOR UPDATE
        '''), {'leagueId':league_id}).fetchall()]

    def close(self, conn, league_id, week_id, next_week_id):
        conn.execute(text('''UPDATE "Week" SET "scoringComplete"=true, "isLocked"=true
            WHERE id=:weekId AND "leagueId"=:leagueId'''),{'weekId':week_id,'leagueId':league_id})
        if next_week_id is not None:
            conn.execute(text('''UPDATE "Week" SET "isLocked"=true
                WHERE id=:weekId AND "leagueId"=:leagueId'''),{'weekId':next_week_id,'leagueId':league_id})
