"""Pre-draft capacity; caller owns the league lock and transaction."""
import json
from decimal import Decimal, InvalidOperation
from sqlalchemy import text
from .conference_caps import require_conference_cap
from .conference_membership import conference_sql


def calculate_rounds(num_players, max_rounds, conferences):
    if isinstance(num_players, bool) or not isinstance(num_players, int) or num_players <= 0:
        raise ValueError('Draft capacity requires a positive number of owners')
    try:
        maximum = Decimal(str(max_rounds))
        if not maximum.is_finite() or maximum <= 0 or maximum != int(maximum):
            raise ValueError('Invalid maximum draft rounds')
    except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
        raise ValueError('Invalid maximum draft rounds') from exc
    capacity = 0
    for conference in conferences:
        cap = require_conference_cap(conference.get('maxTeamsPerOwner'), conference.get('sportConferenceId'))
        teams = int(conference['teamsInConference'])
        if teams < 0:
            raise ValueError('Invalid conference team count')
        capacity += min(teams, num_players * cap)
    return min(int(maximum), capacity // num_players)


def refresh_draft_capacity(conn, league_id):
    """Resize only pre-draft leagues, from actual members and effective season teams."""
    row = conn.execute(text('''
        SELECT l.settings, l.sport, l."seasonYear", l.status,
               s."maxDraftRounds",
               EXISTS (SELECT 1 FROM "DraftState" ds WHERE ds."leagueId"=l.id AND ds.status<>'pre') AS "hasStarted",
               (SELECT COUNT(*) FROM "LeagueMember" lm WHERE lm."leagueId"=l.id) AS "memberCount"
        FROM "League" l JOIN "Sport" s ON s.id=l.sport
        WHERE l.id=:leagueId
    '''), {'leagueId': league_id}).fetchone()
    if not row:
        raise ValueError('League draft configuration unavailable')
    league = dict(row._mapping)
    if league['status'] != 'Pre-Draft' or league['hasStarted']:
        return None
    conferences = conn.execute(text(conference_sql('''
        SELECT sc.id AS "sportConferenceId", sc."maxTeamsPerOwner",
               COUNT(cm."sportTeamId") AS "teamsInConference"
        FROM "SportConference" sc
        LEFT JOIN "ConferenceMembership" cm ON cm."sportConferenceId"=sc.id
        WHERE sc."sportId"=:sportId
        GROUP BY sc.id, sc."maxTeamsPerOwner"
    ''', ':seasonYear')), {'sportId': league['sport'], 'seasonYear': league['seasonYear']}).fetchall()
    num_players = int(league['memberCount'])
    rounds = calculate_rounds(num_players, league['maxDraftRounds'], [dict(r._mapping) for r in conferences])
    settings = dict(league['settings'] or {})
    settings['draft'] = {**(settings.get('draft') or {}), 'numberOfRounds': rounds}
    conn.execute(text('''
        UPDATE "League" SET "numPlayers"=:capacityPlayers,
            settings=CAST(:capacitySettings AS jsonb), "updatedAt"=now()
        WHERE id=:leagueId
    '''), {'leagueId': league_id, 'capacityPlayers': num_players, 'capacitySettings': json.dumps(settings)})
    return rounds
