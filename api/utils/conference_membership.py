"""Effective conference SQL for trusted repository templates, never user input.

Select by year before validating references: an invalid seasonal row suppresses
current fallback, exposing missing configuration rather than hiding dirty data.
The existing per-team/sport partial unique indexes establish single cardinality.
"""

from .conference_caps import require_conference_cap

def conference_sql(statement, year_expression):
    relation = f'''(
        SELECT selected_membership.*
        FROM "ConferenceMembership" selected_membership
        JOIN "SportTeam" membership_team
          ON membership_team.id=selected_membership."sportTeamId"
         AND membership_team."sportId"=selected_membership."sportId"
        JOIN "SportConference" membership_conference
          ON membership_conference.id=selected_membership."sportConferenceId"
         AND membership_conference."sportId"=selected_membership."sportId"
        WHERE selected_membership."seasonYear"=({year_expression})
           OR (selected_membership."seasonYear" IS NULL AND NOT EXISTS (
               SELECT 1 FROM "ConferenceMembership" seasonal_membership
               WHERE seasonal_membership."sportTeamId"=selected_membership."sportTeamId"
                 AND seasonal_membership."seasonYear"=({year_expression})
           ))
    )'''
    return statement.replace('"ConferenceMembership"', relation)


def require_conference_mappings(conn, league_id, team_ids):
    """Fail closed for affected teams; no implicit independent/uncapped bucket."""
    from sqlalchemy import text
    requested = set(team_ids)
    if not requested:
        return {}
    team_params = {f'mappingTeam{index}': team for index, team in enumerate(sorted(requested))}
    team_placeholders = ','.join(':'+key for key in team_params)
    statement = conference_sql(f'''
        SELECT st.id AS "sportTeamId", sc.id AS "sportConferenceId", sc."maxTeamsPerOwner"
        FROM "SportTeam" st JOIN "League" l ON l.id=:membershipLeagueId AND l.sport=st."sportId"
        JOIN "ConferenceMembership" cm ON cm."sportTeamId"=st.id AND cm."sportId"=l.sport
        JOIN "SportConference" sc ON sc.id=cm."sportConferenceId" AND sc."sportId"=l.sport
        WHERE st.id IN ({team_placeholders})
    ''', '(SELECT "seasonYear" FROM "League" WHERE id=:membershipLeagueId)')
    rows = conn.execute(text(statement), {'membershipLeagueId': league_id, **team_params}).fetchall()
    result = {int(row._mapping['sportTeamId']): dict(row._mapping) for row in rows}
    if set(result) != requested:
        raise ValueError('Conference configuration unavailable for team(s)')
    for mapping in result.values():
        mapping['maxTeamsPerOwner'] = require_conference_cap(mapping.get('maxTeamsPerOwner'), mapping['sportConferenceId'])
    return result


def require_member_roster_mappings(conn, league_id, member_ids, week_number, extra_team_ids=()):
    from sqlalchemy import text
    member_params = {f'mappingMember{index}': member for index, member in enumerate(member_ids)}
    if not member_params:
        return require_conference_mappings(conn, league_id, extra_team_ids)
    member_placeholders = ','.join(':'+key for key in member_params)
    rows = conn.execute(text(f'''SELECT DISTINCT "sportTeamId" FROM "LeagueTeamSlot"
        WHERE "leagueId"=:mappingLeagueId AND "memberId" IN ({member_placeholders})
          AND "acquiredWeek"<=:mappingWeek AND ("droppedWeek" IS NULL OR "droppedWeek">:mappingWeek)
    '''), {'mappingLeagueId': league_id, **member_params, 'mappingWeek': week_number}).fetchall()
    return require_conference_mappings(conn, league_id, list(extra_team_ids)+[row._mapping['sportTeamId'] for row in rows])
