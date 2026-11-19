"""League-wide daily games with ownership at each game's scoring week."""
import datetime as dt
import re
from zoneinfo import ZoneInfo
from flask import request, jsonify
from sqlalchemy import text
from actors import UserActor
from authenticatedPrincipal import resolve_authenticated_principal, PrincipalResolutionError
from utils.authorization import league_read_scope
from utils.conference_membership import conference_sql
from utils.requestValidation import integer_field
from rules.leagueRules import parse_settings, get_timezone_name_from_settings
from endpoints.roster.contracts import RosterAccessDenied


def daily_bounds(day, timezone):
    if not isinstance(day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', day):
        raise ValueError('date must be YYYY-MM-DD')
    date = dt.date.fromisoformat(day)
    zone = ZoneInfo(timezone)
    start = dt.datetime.combine(date, dt.time(), zone)
    end = dt.datetime.combine(date + dt.timedelta(days=1), dt.time(), zone)
    return start.astimezone(dt.timezone.utc), end.astimezone(dt.timezone.utc)


class DailyScoreboardRepository:
    def league(self, conn, league_id, user_id):
        scope, params = league_read_scope(league_id, user_id)
        row = conn.execute(text('''SELECT l.sport, l."seasonYear", l.settings,
            ss.id AS "sportSeasonId" FROM "League" l JOIN "SportSeason" ss
            ON ss."sportId"=l.sport AND ss."seasonYear"=l."seasonYear"
            WHERE l.id=:leagueId ''' + scope), {'leagueId': league_id, **params}).fetchone()
        return dict(row._mapping) if row else None

    def games(self, conn, params):
        scope, reader_params = league_read_scope(params['leagueId'], params['readerUserId'])
        sql = conference_sql('''SELECT gr.id, gr."externalGameId", gr.date,
            gr."timeTBD", gr."isCompleted", gr.broadcast,
            gr."homeTeamId", COALESCE(home_school.name,gr."homeTeamName") AS "homeTeamName", gr."homeScore",
            gr."awayTeamId", COALESCE(away_school.name,gr."awayTeamName") AS "awayTeamName", gr."awayScore",
            hc.name AS "homeConferenceName", ac.name AS "awayConferenceName",
            hw."weekNumber" AS "ownershipWeekNumber",
            hm.id AS "homeOwnerMemberId", hm."teamName" AS "homeOwnerTeamName",
            hu."displayName" AS "homeOwnerDisplayName",
            am.id AS "awayOwnerMemberId", am."teamName" AS "awayOwnerTeamName",
            au."displayName" AS "awayOwnerDisplayName"
            FROM "GameResult" gr
            LEFT JOIN "SportTeam" home_name_team ON home_name_team.id=gr."homeTeamId" AND home_name_team."sportId"=gr.sport
            LEFT JOIN "School" home_school ON home_school.id=home_name_team."schoolId"
            LEFT JOIN "SportTeam" away_name_team ON away_name_team.id=gr."awayTeamId" AND away_name_team."sportId"=gr.sport
            LEFT JOIN "School" away_school ON away_school.id=away_name_team."schoolId"
            LEFT JOIN "ConferenceMembership" hcm ON hcm."sportTeamId"=gr."homeTeamId" AND hcm."sportId"=:sport
            LEFT JOIN "SportConference" hsc ON hsc.id=hcm."sportConferenceId" AND hsc."sportId"=:sport
            LEFT JOIN "Conference" hc ON hc.id=hsc."conferenceId"
            LEFT JOIN "ConferenceMembership" acm ON acm."sportTeamId"=gr."awayTeamId" AND acm."sportId"=:sport
            LEFT JOIN "SportConference" asc_ ON asc_.id=acm."sportConferenceId" AND asc_."sportId"=:sport
            LEFT JOIN "Conference" ac ON ac.id=asc_."conferenceId"
            LEFT JOIN LATERAL (
                SELECT w."weekNumber" FROM "Week" w WHERE w."leagueId"=:leagueId
                  AND gr.date >= COALESCE(w."startDate", w."endDate" + interval '1 microsecond' - interval '7 days')
                  AND gr.date <= w."endDate" ORDER BY w."weekNumber" DESC LIMIT 1
            ) hw ON true
            LEFT JOIN LATERAL (
                SELECT lts."memberId" FROM "LeagueTeamSlot" lts
                WHERE lts."leagueId"=:leagueId AND lts."sportTeamId"=gr."homeTeamId"
                  AND lts."acquiredWeek"<=hw."weekNumber"
                  AND (lts."droppedWeek" IS NULL OR lts."droppedWeek">hw."weekNumber")
                ORDER BY lts."acquiredWeek" DESC, lts.id DESC LIMIT 1
            ) ho ON true
            LEFT JOIN "LeagueMember" hm ON hm.id=ho."memberId" AND hm."leagueId"=:leagueId
            LEFT JOIN "User" hu ON hu.id=hm."userId"
            LEFT JOIN LATERAL (
                SELECT lts."memberId" FROM "LeagueTeamSlot" lts
                WHERE lts."leagueId"=:leagueId AND lts."sportTeamId"=gr."awayTeamId"
                  AND lts."acquiredWeek"<=hw."weekNumber"
                  AND (lts."droppedWeek" IS NULL OR lts."droppedWeek">hw."weekNumber")
                ORDER BY lts."acquiredWeek" DESC, lts.id DESC LIMIT 1
            ) ao ON true
            LEFT JOIN "LeagueMember" am ON am.id=ao."memberId" AND am."leagueId"=:leagueId
            LEFT JOIN "User" au ON au.id=am."userId"
            WHERE gr.sport=:sport AND gr."sportSeasonId"=:sportSeasonId
              AND gr.date>=:dayStart AND gr.date<:dayEnd
            ''' + scope + ''' ORDER BY gr.date, gr."externalGameId"''', ':seasonYear')
        rows = conn.execute(text(sql), {**params, **reader_params})
        return [dict(row._mapping) for row in rows]


class DailyScoreboardService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository or DailyScoreboardRepository()

    def read(self, actor, league_id, day):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        with self.engine.connect() as conn:
            context = self.repository.league(conn, league_id, actor.user_id)
            if context is None:
                raise RosterAccessDenied('League not found')
            timezone = get_timezone_name_from_settings(parse_settings(context.get('settings'))) or 'UTC'
            start, end = daily_bounds(day, timezone)
            games = self.repository.games(conn, {**context, 'leagueId': league_id,
                'readerUserId': actor.user_id, 'dayStart': start, 'dayEnd': end})
            if self.repository.league(conn, league_id, actor.user_id) is None:
                raise RosterAccessDenied('League not found')
            return {'date': day, 'timezone': timezone, 'games': games}


class DailyScoreboardEndpoints:
    def __init__(self, engine):
        self.engine = engine
        self.service = DailyScoreboardService(engine)

    def read(self):
        try:
            principal = resolve_authenticated_principal(self.engine)
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict):
                return jsonify(message='Request body must be a JSON object'), 400
            result = self.service.read(UserActor(principal.user_id, principal.subject),
                integer_field(payload, 'leagueId'), payload.get('date'))
            return jsonify(result)
        except PrincipalResolutionError as exc:
            return jsonify(error=exc.code), exc.status_code
        except RosterAccessDenied:
            return jsonify(message='League not found'), 404
        except ValueError as exc:
            return jsonify(message=str(exc)), 400
