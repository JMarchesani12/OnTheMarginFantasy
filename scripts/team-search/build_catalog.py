"""Build offline search data from explicitly downloaded public ESPN team lists.

Usage: python3 scripts/team-search/build_catalog.py /path/to/*-team-names.json
No network access, database writes, or name changes. See README.md.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'api/data/team_search_aliases.json'


def build(paths):
    schools = {}
    sources = set()
    for path in paths:
        data = json.loads(path.read_text())
        for sport in data['sports']:
            for league in sport['leagues']:
                sources.add(f"https://site.api.espn.com/apis/site/v2/sports/{sport['slug']}/{league['slug']}/teams?limit=1000&groups=50")
                for record in league['teams']:
                    team = record['team']
                    entry = schools.setdefault(team['id'], {'names': set(), 'schoolNames': set(), 'mascots': set(), 'label': team['location']})
                    for key in ('location', 'displayName', 'shortDisplayName', 'abbreviation'):
                        if team.get(key):
                            entry['names'].add(team[key])
                            if key != 'displayName': entry['schoolNames'].add(team[key])
                    if team.get('name'): entry['mascots'].add(team['name'])
    overrides = json.loads((Path(__file__).with_name('overrides.json')).read_text())
    for override in overrides:
        entry = schools.get(override['espnId'])
        if entry is None:
            raise ValueError(f"Override school missing from inputs: {override['espnId']}")
        entry['names'].update(override['aliases'])
        entry['schoolNames'].update(override['aliases'])
    # Only known mascot suffixes may extend an alternate school name. Arbitrary
    # prefixes such as USC in USC Upstate must not confer another school's aliases.
    for entry in schools.values():
        entry['names'].update(f'{school} {mascot}' for school in entry['schoolNames'] for mascot in entry['mascots'])
    return {
        'version': 1,
        'sources': sorted(sources),
        'groups': [{'id': identity, 'label': entry['label'], 'names': sorted(entry['names'])}
                   for identity, entry in sorted(schools.items(), key=lambda row: int(row[0]))],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputs', type=Path, nargs='*')
    args = parser.parse_args()
    if not args.inputs: parser.error('Provide downloaded source files')
    output = json.dumps(build(args.inputs), ensure_ascii=False, indent=2) + '\n'
    BACKEND.write_text(output)
    print('Offline school alias seed rebuilt; runtime aliases remain in the database.')



if __name__ == '__main__': main()
