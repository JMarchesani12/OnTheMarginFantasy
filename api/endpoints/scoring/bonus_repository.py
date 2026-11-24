"""Bonus-only facts; season tiebreakers keep their existing historical scope."""
import json
from sqlalchemy import text
from utils.conference_membership import conference_sql
from rules.playoffCoverage import expected_round_counts
from .standings_repository import ConferenceStandingsRepository


class SeasonBonusRepository:
    def context(self, conn, league_id):
        row = conn.execute(text('''SELECT ss.id AS "sportSeasonId",l.settings,
            COALESCE((SELECT MAX(w."weekNumber") FROM "Week" w WHERE w."leagueId"=l.id AND w."startDate"<=now()),
                     (SELECT MIN(w."weekNumber") FROM "Week" w WHERE w."leagueId"=l.id)) AS "weekNumber"
            FROM "League" l JOIN "SportSeason" ss ON ss."sportId"=l.sport AND ss."seasonYear"=l."seasonYear"
            WHERE l.id=:league'''), {'league':league_id}).fetchone()
        if not row: return None
        context=dict(row._mapping)
        settings=context.pop('settings') or {}
        if isinstance(settings,str): settings=json.loads(settings)
        context['subdivision']=settings.get('subdivision')
        return context

    def roster(self, conn, league_id, week_number):
        sql = conference_sql('''SELECT lts."memberId",lts."sportTeamId",cm."sportConferenceId"
            FROM "LeagueTeamSlot" lts JOIN "League" l ON l.id=lts."leagueId"
            JOIN "SportTeam" st ON st.id=lts."sportTeamId" AND st."sportId"=l.sport
            LEFT JOIN "ConferenceMembership" cm ON cm."sportTeamId"=st.id AND cm."sportId"=l.sport
            WHERE lts."leagueId"=:league AND lts."acquiredWeek"<=:week
              AND (lts."droppedWeek" IS NULL OR lts."droppedWeek">:week)
            ORDER BY lts."memberId",lts."sportTeamId"''', '(SELECT "seasonYear" FROM "League" WHERE id=:league)')
        return [dict(row._mapping) for row in conn.execute(text(sql),{'league':league_id,'week':week_number}).fetchall()]

    def snapshots(self, conn, season_id):
        return ConferenceStandingsRepository().latest_validated(conn,season_id)

    def tournaments(self, conn, season_id):
        rows = conn.execute(text('''SELECT sp.id,td.code,
            EXTRACT(YEAR FROM COALESCE((SELECT MAX(sd."regularSeasonEnd") FROM "SportSeasonSubdivision" sd
                WHERE sd."sportSeasonId"=ss.id AND sd.code=CASE td.code WHEN 'FBS_PLAYOFFS' THEN 'FBS' WHEN 'FCS_PLAYOFFS' THEN 'FCS' ELSE 'D1' END),ss."seasonEnd")) AS "sourceYear",
            COALESCE(COALESCE(sp."endDate", (SELECT MAX(sd."postseasonEnd") FROM "SportSeasonSubdivision" sd
                WHERE sd."sportSeasonId"=ss.id AND sd.code=CASE td.code WHEN 'FBS_PLAYOFFS' THEN 'FBS' WHEN 'FCS_PLAYOFFS' THEN 'FCS' ELSE 'D1' END)) < now(),false) AS ended
            FROM "SeasonPhase" sp JOIN "TournamentDefinition" td ON td.id=sp."tournamentId"
            JOIN "SportSeason" ss ON ss.id=sp."sportSeasonId" AND ss."sportId"=td."sportId"
            WHERE sp."sportSeasonId"=:season AND td.scope='National'
              AND td.code IN ('NCAA_TOURNEY','FCS_PLAYOFFS','FBS_PLAYOFFS')'''),{'season':season_id}).fetchall()
        result=[dict(row._mapping) for row in rows]
        for tournament in result:
            tournament['expectedRoundCounts']=expected_round_counts(tournament['code'],int(tournament['sourceYear']))
        return result

    def frozen(self, conn, league_id):
        row = conn.execute(text('SELECT result FROM "SeasonBonusResult" WHERE "leagueId"=:league'),{'league':league_id}).fetchone()
        if not row: return None
        result = row[0]
        return json.loads(result) if isinstance(result,str) else result

    def playoff_games(self, conn, season_id, phase_id):
        return [dict(row._mapping) for row in conn.execute(text('''SELECT "homeTeamId","awayTeamId","homeScore","awayScore",
            "roundOrder","isCompleted","bonusTournamentCode" FROM "GameResult"
            WHERE "sportSeasonId"=:season AND "seasonPhaseId"=:phase ORDER BY date,id'''),
            {'season':season_id,'phase':phase_id}).fetchall()]
