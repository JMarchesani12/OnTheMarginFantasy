"""Week-based ownership reads. Caller owns connection, result and transaction.

Scalar draft counts deliberately use distinct teams; grouped free-agent counts
use active rows. These variants preserve legacy result and league-existence
semantics rather than imposing new authorization/configuration policy.
"""
from sqlalchemy import text
from .conference_membership import conference_sql


_ACTIVE_WEEK = '''lts."acquiredWeek" <= :week_number
    AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :week_number)'''
_ANY_MEMBER = object()


def _effective_statement(statement):
    return text(conference_sql(statement, '(SELECT "seasonYear" FROM "League" WHERE id=:league_id)'))


def team_ownership_rows(conn, league_id, team_id, week_number, member_id=_ANY_MEMBER):
    # Omission means league-wide; an explicitly supplied NULL must stay member-scoped.
    member_filter = '' if member_id is _ANY_MEMBER else 'AND lts."memberId" = :member_id'
    params = {'league_id': league_id, 'team_id': team_id, 'week_number': week_number}
    if member_id is not _ANY_MEMBER:
        params['member_id'] = member_id
    return conn.execute(text(f'''
        SELECT 1 FROM "LeagueTeamSlot" lts
        WHERE lts."leagueId" = :league_id AND lts."sportTeamId" = :team_id
          AND {_ACTIVE_WEEK}
          {member_filter}
        LIMIT 1
    '''), params)


def distinct_conference_count_rows(conn, league_id, member_id, week_number, conference_id):
    return conn.execute(_effective_statement(f'''
        WITH league_info AS (
            SELECT "seasonYear" FROM "League" WHERE id = :league_id
        ), owned AS (
            SELECT lts."sportTeamId" FROM "LeagueTeamSlot" lts
            WHERE lts."leagueId" = :league_id AND lts."memberId" = :member_id
              AND {_ACTIVE_WEEK}
        )
        SELECT COUNT(DISTINCT o."sportTeamId")::int AS cnt
        FROM owned o
        JOIN "SportTeam" st ON st.id = o."sportTeamId"
        JOIN "ConferenceMembership" cm
          ON cm."sportTeamId" = st.id AND cm."sportId" = st."sportId"
        CROSS JOIN league_info li
        JOIN "SportConference" sc
          ON sc.id = cm."sportConferenceId" AND sc."sportId" = st."sportId"
        WHERE sc.id = :conference_id
          AND (cm."seasonYear" IS NULL OR cm."seasonYear" = li."seasonYear")
    '''), {'league_id': league_id, 'member_id': member_id,
           'week_number': week_number, 'conference_id': conference_id})


def grouped_conference_count_rows(conn, league_id, member_id, week_number):
    return conn.execute(_effective_statement(f'''
        SELECT cm."sportConferenceId" AS "sportConferenceId", COUNT(*) AS "cnt"
        FROM "LeagueTeamSlot" lts
        JOIN "ConferenceMembership" cm ON cm."sportTeamId" = lts."sportTeamId"
        WHERE lts."leagueId" = :league_id AND lts."memberId" = :member_id
          AND {_ACTIVE_WEEK}
        GROUP BY cm."sportConferenceId"
    '''), {'league_id': league_id, 'member_id': member_id, 'week_number': week_number})
