"""Finalization persistence; all operations use the caller's transaction."""
from sqlalchemy import text


class SeasonFinalizationRepository:
    def candidates(self, conn, today):
        return [int(row._mapping['id']) for row in conn.execute(text('''
            SELECT id FROM "SportSeason"
            WHERE "seasonEnd" < :today AND COALESCE("seasonFinalized",false)=false
            ORDER BY id
        '''), {'today': today}).fetchall()]

    def lock_season(self, conn, season_id, today):
        row = conn.execute(text('''
            SELECT id,"sportId","seasonYear","seasonFinalized",("seasonEnd" < :today) AS ended
            FROM "SportSeason" WHERE id=:seasonId FOR UPDATE
        '''), {'seasonId': season_id, 'today': today}).fetchone()
        return dict(row._mapping) if row is not None else None

    def scope_ids(self, conn, sport_id, year):
        return [int(row._mapping['id']) for row in conn.execute(text('''
            SELECT id FROM "League" WHERE sport=:sportId AND "seasonYear"=:year ORDER BY id
        '''), {'sportId': sport_id, 'year': year}).fetchall()]

    def lock_league(self, conn, league_id):
        row = conn.execute(text('''SELECT id,sport,"seasonYear" FROM "League"
            WHERE id=:leagueId FOR UPDATE'''), {'leagueId': league_id}).fetchone()
        return dict(row._mapping) if row is not None else None

    def weeks(self, conn, league_id, now):
        return [dict(row._mapping) for row in conn.execute(text('''
            SELECT id,"weekNumber",("startDate" IS NOT NULL AND "endDate" IS NOT NULL
                AND "startDate" <= "endDate" AND "endDate" < :now
                AND "scoringComplete"=true) AS ready
            FROM "Week" WHERE "leagueId"=:leagueId ORDER BY "weekNumber" FOR UPDATE
        '''), {'leagueId': league_id, 'now': now}).fetchall()]

    def pending(self, conn, league_id):
        return conn.execute(text('''SELECT id FROM "Transaction"
            WHERE "leagueId"=:leagueId AND status='PENDING_APPLY' ORDER BY id FOR UPDATE
        '''), {'leagueId': league_id}).fetchall()

    def member_ids(self, conn, league_id):
        return [int(row._mapping['id']) for row in conn.execute(text('''
            SELECT id FROM "LeagueMember" WHERE "leagueId"=:leagueId ORDER BY id FOR UPDATE
        '''), {'leagueId': league_id}).fetchall()]

    def mark_league(self, conn, league_id):
        conn.execute(text('''UPDATE "League" SET status='Completed',"updatedAt"=now()
            WHERE id=:leagueId'''), {'leagueId': league_id})

    def mark_season(self, conn, season_id):
        conn.execute(text('''UPDATE "SportSeason" SET "seasonFinalized"=true
            WHERE id=:seasonId'''), {'seasonId': season_id})
