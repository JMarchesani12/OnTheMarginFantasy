"""Batch team analytics, independent of ownership and restricted to confirmed finals."""
from sqlalchemy import text
from actors import UserActor
from utils.authorization import league_read_scope
from rules.leagueRules import resolve_rules, adjust_margin
from rules.tournamentRules import score_margin
from .contracts import RosterAccessDenied, RosterWeekUnavailable


def summarize_team_performance(team_ids, games, sport, rules):
    totals = {team_id: dict(teamId=team_id, weekDifferential=0, seasonDifferential=0,
                           weekGamesPlayed=0, gamesPlayed=0, averageDifferential=None,
                           unconfirmedGames=0) for team_id in team_ids}
    seen = set()
    for game in games:
        if game['id'] in seen:
            continue
        seen.add(game['id'])
        for side, opponent in (('home', 'away'), ('away', 'home')):
            total = totals.get(game[f'{side}TeamId'])
            if total is None:
                continue
            if game.get('isCompleted') is None:
                total['unconfirmedGames'] += 1
            if game.get('isCompleted') is not True:
                continue
            matchup_rules = rules
            if sport == 1 and game.get(f'{opponent}TeamUnranked'):
                matchup_rules = {**rules, 'minimumTierGap': 1}
            margin = game[f'{side}Score'] - game[f'{opponent}Score']
            adjusted = adjust_margin(margin, game[f'{side}TeamTier'],
                                     game[f'{opponent}TeamTier'], matchup_rules)['adjustedMargin']
            points = score_margin(adjusted, game.get('phaseRules') or {})
            total['seasonDifferential'] += points
            total['gamesPlayed'] += 1
            if game['inWeek']:
                total['weekDifferential'] += points
                total['weekGamesPlayed'] += 1
    for total in totals.values():
        if total['gamesPlayed']:
            total['averageDifferential'] = round(total['seasonDifferential'] / total['gamesPlayed'], 2)
    return list(totals.values())


class TeamPerformanceRepository:
    def context(self, conn, league_id, week_number, user_id):
        scope, params = league_read_scope(league_id, user_id)
        row = conn.execute(text('''SELECT l.sport, l.settings, ss.id AS "sportSeasonId",
            w.id AS "weekId", COALESCE(w."startDate", w."endDate" + interval '1 microsecond' - interval '7 days') AS "startDate",
            w."endDate" FROM "League" l
            JOIN "SportSeason" ss ON ss."sportId"=l.sport AND ss."seasonYear"=l."seasonYear"
            LEFT JOIN "Week" w ON w."leagueId"=l.id AND w."weekNumber"=:weekNumber
            WHERE l.id=:leagueId ''' + scope),
            dict(leagueId=league_id, weekNumber=week_number, **params)).fetchone()
        return dict(row._mapping) if row else None

    def teams(self, conn, sport):
        return [r[0] for r in conn.execute(text('SELECT id FROM "SportTeam" WHERE "sportId"=:sport'), {'sport': sport})]

    def games(self, conn, context):
        # JSON projection tolerates a deployment before the completion-status migration.
        rows = conn.execute(text('''WITH tiers AS (
            SELECT COALESCE(MAX(tier),0)+1 AS fallback FROM "SportTeam" WHERE "sportId"=:sport
        ) SELECT gr.id, gr."homeTeamId", gr."awayTeamId", gr."homeScore", gr."awayScore",
            (to_jsonb(gr)->>'isCompleted')::boolean AS "isCompleted",
            COALESCE(h.tier,t.fallback) AS "homeTeamTier", COALESCE(a.tier,t.fallback) AS "awayTeamTier",
            (h.tier IS NULL) AS "homeTeamUnranked", (a.tier IS NULL) AS "awayTeamUnranked",
            COALESCE(sp.rules,'{}'::jsonb) AS "phaseRules",
            (gr.date BETWEEN :startDate AND :endDate) AS "inWeek"
            FROM "GameResult" gr CROSS JOIN tiers t
            LEFT JOIN "SportTeam" h ON h.id=gr."homeTeamId"
            LEFT JOIN "SportTeam" a ON a.id=gr."awayTeamId"
            LEFT JOIN "SeasonPhase" sp ON sp.id=gr."seasonPhaseId"
            WHERE gr.sport=:sport AND gr."sportSeasonId"=:sportSeasonId AND gr.date<=now()
            ORDER BY gr.id'''), context)
        return [dict(row._mapping) for row in rows]


class TeamPerformanceService:
    def __init__(self, engine, repository=None):
        self.engine = engine
        self.repository = repository or TeamPerformanceRepository()

    def read(self, actor, league_id, week_number):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        with self.engine.connect() as conn:
            context = self.repository.context(conn, league_id, week_number, actor.user_id)
            if context is None:
                raise RosterAccessDenied('League not found')
            if context['weekId'] is None:
                raise RosterWeekUnavailable('Scoring week not found')
            teams = self.repository.teams(conn, context['sport'])
            games = self.repository.games(conn, context)
            if self.repository.context(conn, league_id, week_number, actor.user_id) is None:
                raise RosterAccessDenied('League not found')
            return {'weekNumber': week_number, 'teams': summarize_team_performance(
                teams, games, context['sport'], resolve_rules(context['sport'], context.get('settings')))}
