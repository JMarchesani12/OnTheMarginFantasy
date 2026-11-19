"""Reviewed canonical school-name planning; provider IDs never equal school IDs."""


def plan_school_names(schools, teams, catalog):
    labels={str(group['id']):group['label'].strip() for group in catalog['groups']}
    by_school={};provider_schools={}
    for team in teams:
        if team.get('externalId'):
            provider_schools.setdefault(str(team['externalId']),set()).add(team['schoolId'])
    if any(len(school_ids)>1 for school_ids in provider_schools.values()):
        raise ValueError('Ambiguous provider ID maps to multiple schools')
    for team in teams:
        label=labels.get(str(team.get('externalId')))
        if label: by_school.setdefault(team['schoolId'],set()).add(label)
    if any(len(names)>1 for names in by_school.values()):
        raise ValueError('Ambiguous provider labels for a school')
    updates=[];unmapped=[]
    for school in schools:
        names=by_school.get(school['id'])
        if not names: unmapped.append(school['id']);continue
        new_name=next(iter(names))
        if school['name']!=new_name:
            updates.append(dict(schoolId=school['id'],oldName=school['name'],newName=new_name))
    return dict(updates=updates,unmappedSchoolIds=unmapped)
