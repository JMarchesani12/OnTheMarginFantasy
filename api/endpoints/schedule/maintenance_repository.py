"""Maintenance SQL; every operation uses the caller's connection/transaction."""
from sqlalchemy import text


class CalendarMaintenanceRepository:
    def discover(self, conn, year, league_ids=None):
        if league_ids is None:
            return [int(r._mapping['id']) for r in conn.execute(text('SELECT id FROM "League" WHERE "seasonYear"=:year ORDER BY id'), {'year':year}).fetchall()], []
        ids, errors = [], []
        for league_id in sorted(set(league_ids)):
            row = conn.execute(text('SELECT id,"seasonYear" FROM "League" WHERE id=:id'), {'id':league_id}).fetchone()
            if row is None:
                errors.append({'leagueId':league_id,'reason':'not_found'})
            elif row._mapping['seasonYear'] != year:
                errors.append({'leagueId':league_id,'reason':'wrong_season'})
            else:
                ids.append(league_id)
        return ids, errors

    def league(self, conn, league_id, lock=False):
        row = conn.execute(text('SELECT id,sport,"seasonYear",status,settings FROM "League" WHERE id=:id'+(' FOR UPDATE' if lock else '')), {'id':league_id}).fetchone()
        return dict(row._mapping) if row is not None else None

    def season(self, conn, sport, year, lock=False):
        row = conn.execute(text('SELECT id,"sportId","seasonYear","seasonFinalized" FROM "SportSeason" WHERE "sportId"=:sport AND "seasonYear"=:year'+(' FOR UPDATE' if lock else '')), {'sport':sport,'year':year}).fetchone()
        return dict(row._mapping) if row is not None else None

    def draft_state(self, conn, league_id, lock=False):
        row = conn.execute(text('SELECT status,"currentOverallPickNumber","currentMemberId","expiresAt","lastPickAt" FROM "DraftState" WHERE "leagueId"=:id'+(' FOR UPDATE' if lock else '')), {'id':league_id}).fetchone()
        return dict(row._mapping) if row is not None else None

    def weeks(self, conn, league_id, lock=False):
        return [dict(r._mapping) for r in conn.execute(text('SELECT id,"weekNumber","startDate","endDate","isLocked","scoringComplete" FROM "Week" WHERE "leagueId"=:id ORDER BY "weekNumber"'+(' FOR UPDATE' if lock else '')), {'id':league_id}).fetchall()]

    def histories(self, conn, league_id):
        params = {'id':league_id}
        picks = conn.execute(text('SELECT count(*) AS n FROM "DraftPick" WHERE "leagueId"=:id'),params).fetchone()._mapping['n']
        ownership = [dict(r._mapping) for r in conn.execute(text('SELECT id,"memberId","sportTeamId","acquiredWeek","droppedWeek" FROM "LeagueTeamSlot" WHERE "leagueId"=:id ORDER BY id'),params).fetchall()]
        # Even malformed foreign-league references must block cascading deletion.
        scope = 'WHERE "leagueId"=:id OR "weekId" IN (SELECT id FROM "Week" WHERE "leagueId"=:id)'
        transactions = [dict(r._mapping) for r in conn.execute(text('SELECT id,"leagueId","weekId",status FROM "Transaction" '+scope+' ORDER BY id'),params).fetchall()]
        scores = [dict(r._mapping) for r in conn.execute(text('SELECT id,"weekId","memberId","pointsAwarded" FROM "WeeklyTeamScore" '+scope+' ORDER BY id'),params).fetchall()]
        return {'draftPicks':int(picks),'ownership':ownership,'transactions':transactions,'scores':scores}

    def update_week(self, conn, league_id, week_id, start, end):
        conn.execute(text('UPDATE "Week" SET "startDate"=:start,"endDate"=:end WHERE id=:weekId AND "leagueId"=:leagueId'), {'start':start,'end':end,'weekId':week_id,'leagueId':league_id})

    def insert_week(self, conn, league_id, number, start, end):
        return int(conn.execute(text('''INSERT INTO "Week" ("leagueId","weekNumber","startDate","endDate","isLocked","scoringComplete")
            VALUES (:leagueId,:weekNumber,:startDate,:endDate,false,false) RETURNING id'''), {'leagueId':league_id,'weekNumber':number,'startDate':start,'endDate':end}).fetchone()._mapping['id'])

    def delete_unreferenced_week(self, conn, league_id, week_id):
        row = conn.execute(text('''DELETE FROM "Week" AS w WHERE w.id=:weekId AND w."leagueId"=:leagueId
            AND NOT EXISTS (SELECT 1 FROM "Transaction" t WHERE t."weekId"=w.id)
            AND NOT EXISTS (SELECT 1 FROM "WeeklyTeamScore" s WHERE s."weekId"=w.id)
            RETURNING id'''), {'leagueId':league_id,'weekId':week_id}).fetchone()
        if row is None:
            raise ValueError('Week removal refused')

    def close_week(self, conn, league_id, week_id, next_week_id):
        conn.execute(text('UPDATE "Week" SET "scoringComplete"=true,"isLocked"=true WHERE id=:id AND "leagueId"=:leagueId'), {'id':week_id,'leagueId':league_id})
        if next_week_id is not None:
            conn.execute(text('UPDATE "Week" SET "isLocked"=true WHERE id=:id AND "leagueId"=:leagueId'), {'id':next_week_id,'leagueId':league_id})
