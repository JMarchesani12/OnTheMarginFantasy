"""Trusted SQL fragments for legal draft turns; no reservation of future picks."""
from .conference_membership import conference_sql

# DraftPick also counts ownership so all draft acquisitions count regardless of
# the legacy acquiredWeek supplied by a caller. Prior roster slots use week one.
ELIGIBILITY_CTES = conference_sql('''
    WITH draft_teams AS (
        SELECT st.id AS "sportTeamId", sc.id AS "sportConferenceId", sc."maxTeamsPerOwner"
        FROM "League" l
        JOIN "SportTeam" st ON st."sportId"=l.sport
        JOIN "ConferenceMembership" cm ON cm."sportTeamId"=st.id AND cm."sportId"=l.sport
        JOIN "SportConference" sc ON sc.id=cm."sportConferenceId" AND sc."sportId"=l.sport
        WHERE l.id=:leagueId
    ), owned_teams AS (
        SELECT "memberId", "sportTeamId" FROM "DraftPick" WHERE "leagueId"=:leagueId
        UNION
        SELECT "memberId", "sportTeamId" FROM "LeagueTeamSlot"
        WHERE "leagueId"=:leagueId AND "acquiredWeek"<=1 AND ("droppedWeek" IS NULL OR "droppedWeek">1)
    ), owned_counts AS (
        SELECT ot."memberId", mt."sportConferenceId", COUNT(DISTINCT ot."sportTeamId") AS cnt
        FROM owned_teams ot JOIN draft_teams mt ON mt."sportTeamId"=ot."sportTeamId"
        GROUP BY ot."memberId", mt."sportConferenceId"
    ), available_conferences AS (
        SELECT DISTINCT mt."sportConferenceId", mt."maxTeamsPerOwner"
        FROM draft_teams mt
        WHERE NOT EXISTS (SELECT 1 FROM owned_teams ot WHERE ot."sportTeamId"=mt."sportTeamId")
    )
''', '(SELECT "seasonYear" FROM "League" WHERE id=:leagueId)')


def legal_pick_predicate(member_expression):
    """member_expression is a repository-owned alias or bind, never user text."""
    return f'''EXISTS (
        SELECT 1 FROM available_conferences ac
        WHERE ac."maxTeamsPerOwner">COALESCE((
            SELECT oc.cnt FROM owned_counts oc
            WHERE oc."memberId"={member_expression} AND oc."sportConferenceId"=ac."sportConferenceId"
        ),0)
    )'''


def require_draft_caps(conn, league_id):
    """Malformed caps must never masquerade as exhausted draft capacity."""
    from sqlalchemy import text
    from .conference_caps import require_conference_cap
    rows = conn.execute(text('''SELECT sc.id, sc."maxTeamsPerOwner"
        FROM "SportConference" sc JOIN "League" l ON l.sport=sc."sportId"
        WHERE l.id=:leagueId'''), {'leagueId': league_id}).fetchall()
    for row in rows:
        require_conference_cap(row._mapping['maxTeamsPerOwner'], row._mapping['id'])
