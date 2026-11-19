"""Explicit, transaction-owned import of seed aliases into existing school IDs."""
from sqlalchemy import text
from .team_search import normalize_team_search_text


def plan_school_aliases(schools, teams, catalog):
    provider_schools = {}
    names = {}
    def add(school_id, alias, source):
        normalized = normalize_team_search_text(alias)
        if normalized: names.setdefault((school_id, normalized), dict(schoolId=school_id, alias=alias, normalizedAlias=normalized, source=source))
    for school in schools:
        add(school['id'],school['name'],'School')
    for team in teams:
        if team.get('externalId'):
            provider_schools.setdefault(str(team['externalId']),set()).add(team['schoolId'])
    if any(len(schools)>1 for schools in provider_schools.values()):
        raise ValueError('Ambiguous provider ID maps to more than one school')
    for group in catalog['groups']:
        matches=provider_schools.get(str(group['id']))
        if matches:
            school_id=next(iter(matches))
            for alias in group['names']: add(school_id,alias,'ESPN alias seed 2026-11-19')
    return [names[key] for key in sorted(names)]


def import_school_aliases(conn, catalog):
    schools=conn.execute(text('SELECT id,name FROM "School"'),{}).mappings().all()
    teams=conn.execute(text('SELECT "schoolId","externalId" FROM "SportTeam"'),{}).mappings().all()
    rows=plan_school_aliases(schools,teams,catalog)
    # Bounded multi-value inserts avoid one hosted round trip per alias.
    for start in range(0,len(rows),500):
        batch=rows[start:start+500];params={};values=[]
        for index,row in enumerate(batch):
            keys=[f'{key}{index}' for key in row]
            params.update(zip(keys,row.values()))
            values.append('('+','.join(':'+key for key in keys)+')')
        conn.execute(text('INSERT INTO "SchoolAlias" ("schoolId",alias,"normalizedAlias",source) VALUES '+','.join(values)+
                          ' ON CONFLICT ("schoolId","normalizedAlias") DO NOTHING'),params)
    return {'plannedAliases':len(rows),'schools':len({row['schoolId'] for row in rows})}
