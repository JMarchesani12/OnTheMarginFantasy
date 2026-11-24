"""Versioned conference standings on caller-owned connections."""
import json
from sqlalchemy import text
from utils.conference_membership import conference_sql


class ConferenceStandingsRepository:
    def season(self, conn, season_id):
        row = conn.execute(text('''SELECT ss.id,ss."sportId",s."api-keyword" AS "apiKeyword",
            (SELECT MAX("regularSeasonEnd") FROM "SportSeasonSubdivision" WHERE "sportSeasonId"=ss.id) AS "regularEnd"
            FROM "SportSeason" ss JOIN "Sport" s ON s.id=ss."sportId" WHERE ss.id=:season'''),
            {'season': season_id}).fetchone()
        return dict(row._mapping) if row else None

    def teams(self, conn, season_id):
        sql = conference_sql('''SELECT st.id AS "sportTeamId",st."externalId",cm."sportConferenceId"
            FROM "SportTeam" st JOIN "ConferenceMembership" cm ON cm."sportTeamId"=st.id AND cm."sportId"=st."sportId"
            JOIN "SportSeason" ss ON ss."sportId"=st."sportId" AND ss.id=:season
            JOIN "SportConference" sc ON sc.id=cm."sportConferenceId" AND sc."sportId"=ss."sportId"
            WHERE st."externalId" IS NOT NULL''', '(SELECT "seasonYear" FROM "SportSeason" WHERE id=:season)')
        return [dict(row._mapping) for row in conn.execute(text(sql), {'season': season_id}).fetchall()]

    def lock_for_collection(self,conn,season_id):
        conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        row=conn.execute(text('SELECT "seasonFinalized","sportId" FROM "SportSeason" WHERE id=:season FOR SHARE'),{'season':season_id}).fetchone()
        if row is None or row[0]: return False
        conn.execute(text('SELECT id FROM "Sport" WHERE id=:sport FOR SHARE'),{'sport':row[1]}).fetchall()
        conn.execute(text('SELECT id FROM "SportSeasonSubdivision" WHERE "sportSeasonId"=:season FOR SHARE'),{'season':season_id}).fetchall()
        # Configuration writes are rare; stabilize inserts as well as updates
        # while checking complete season membership coverage.
        conn.execute(text('LOCK TABLE "ConferenceMembership","SportTeam","SportConference","SportSeasonSubdivision" IN SHARE MODE'))
        return True

    def save(self, conn, values):
        params = {**values, 'entries': json.dumps(values['entries'])}
        conn.execute(text('''INSERT INTO "ConferenceStandingsSnapshot"
            ("sportSeasonId","sportConferenceId","sourceYear","sourceUrl","regularEnd","isFinal",digest,entries)
            VALUES (:sportSeasonId,:sportConferenceId,:sourceYear,:sourceUrl,:regularEnd,:isFinal,:digest,CAST(:entries AS jsonb))
            ON CONFLICT ("sportSeasonId","sportConferenceId",digest) DO NOTHING'''), params)

    def latest_validated(self, conn, sport_season_id):
        rows = conn.execute(text('''SELECT s.* FROM "ConferenceStandingsSnapshot" s
            WHERE s."sportSeasonId"=:season AND s."isFinal"=true
            AND CURRENT_DATE > s."regularEnd"
            AND s."regularEnd"=(SELECT MAX(sd."regularSeasonEnd") FROM "SportSeasonSubdivision" sd WHERE sd."sportSeasonId"=:season)
            AND NOT EXISTS (SELECT 1 FROM "ConferenceStandingsSnapshot" newer
                WHERE newer."sportSeasonId"=s."sportSeasonId" AND newer."sportConferenceId"=s."sportConferenceId"
                  AND newer."isFinal"=true AND newer.id>s.id)'''), {'season': sport_season_id}).fetchall()
        return [dict(row._mapping) for row in rows]

    def eligible_seasons(self, conn, today):
        return [int(row[0]) for row in conn.execute(text('''SELECT ss.id FROM "SportSeason" ss
            WHERE ss."seasonStart"<=:today AND COALESCE(ss."seasonFinalized",false)=false
            AND ss."sportId" IN (1,2) AND EXISTS (SELECT 1 FROM "League" l
                WHERE l.sport=ss."sportId" AND l."seasonYear"=ss."seasonYear") ORDER BY ss.id'''), {'today': today}).fetchall()]
