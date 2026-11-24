"""Public ESPN conference standings adapter; no database or configured startup.

Conference positions use published regular-season conference records, sharing
positions for equal win percentages; never use playoff seeds, overall records,
poll ranks, or response order. Unsupported groupings remain pending.
"""
from datetime import date
from fractions import Fraction
import re
import requests

BASE_URL = 'https://site.web.api.espn.com/apis/v2/sports'


def provider_year(api_keyword, regular_season_end):
    return date.fromisoformat(str(regular_season_end)[:10]).year


class ESPNStandingsProvider:
    def __init__(self, *, get=None):
        self.get = get or requests.get

    def fetch(self, api_keyword, provider_year, group):
        if api_keyword not in ('basketball/mens-college-basketball', 'football/college-football'):
            raise ValueError('Unsupported standings sport')
        response = self.get(f'{BASE_URL}/{api_keyword}/standings',
                            params={'season': provider_year, 'seasontype': 2, 'level': 3, 'group': group},
                            timeout=15)
        response.raise_for_status()
        return response.json()


def _conference_percentage(stats):
    records=[s for s in stats if s.get('type')=='vsconf']
    if len(records)!=1 or not isinstance(records[0].get('summary'),str):
        raise ValueError('Missing conference record')
    record=records[0]['summary']
    if not re.fullmatch(r'\d+-\d+(?:-\d+)?',record):
        raise ValueError('Invalid conference record')
    parts=list(map(int,record.split('-')))
    wins,losses=parts[:2]
    ties=parts[2] if len(parts)==3 else 0
    total=wins+losses+ties
    if not total:
        raise ValueError('Conference games not played')
    return Fraction(2*wins+ties,2*total),record


def parse_conference_standings(payload, expected_year, expected_group):
    if payload.get('season', {}).get('year') != expected_year or str(payload.get('id')) != str(expected_group):
        raise ValueError('Standings season or subdivision mismatch')
    result = []

    def visit(node):
        standing = node.get('standings')
        combined = False
        if standing is None and node.get('isConference') and node.get('children'):
            divisions=node['children']
            if all(child.get('standings') is not None and not child.get('isConference') for child in divisions):
                for child in divisions:
                    if child['standings'].get('season')!=expected_year or child['standings'].get('seasonType')!=2:
                        raise ValueError('Division standings season mismatch')
                standing={'season':expected_year,'seasonType':2,
                          'entries':[e for child in divisions for e in child['standings'].get('entries',[])]}
                combined=True
        if standing is not None:
            if standing.get('season') != expected_year or standing.get('seasonType') != 2:
                raise ValueError('Standings must be regular-season data for the requested year')
            conference = {'sourceId': str(node['id']), 'name': node.get('name', ''),
                          'status': 'pending', 'reason': 'unverified_conference_placement', 'entries': []}
            independent_groups={('80','18'):'FBS Independents',('81','32'):'FCS Independents'}
            if independent_groups.get((str(expected_group),str(node['id'])))==conference['name']:
                entries=standing.get('entries') or []
                ids=[str(e['team']['id']) for e in entries]
                if ids and len(ids)==len(set(ids)):
                    conference.update(status='ready',reason='independent_no_conference',entries=[
                        {'externalId':identity,'rank':None,'bottomRank':None,'record':None} for identity in ids])
                result.append(conference)
                return
            try:
                name = conference['name'].lower()
                if not node.get('isConference') or 'independent' in name or name.endswith((' - east', ' - west', ' - north', ' - south')):
                    raise ValueError('Not a conference-wide standing')
                entries = standing.get('entries') or []
                seen = set()
                for entry in entries:
                    external_id = str(entry['team']['id'])
                    if external_id in seen:
                        raise ValueError('Duplicate team')
                    seen.add(external_id)
                    stats = entry.get('stats') or []
                    percentage,record = _conference_percentage(stats)
                    conference['entries'].append({'externalId': external_id,'percentage':percentage,'record':record})
                if not entries:
                    raise ValueError('Empty conference')
                for entry in conference['entries']:
                    entry['rank']=1+sum(other['percentage']>entry['percentage'] for other in conference['entries'])
                    entry['bottomRank']=1+sum(other['percentage']<entry['percentage'] for other in conference['entries'])
                for entry in conference['entries']:
                    del entry['percentage']
                conference.update(status='ready', reason=None)
            except (KeyError, TypeError, ValueError):
                conference['entries'] = []
            result.append(conference)
        if not combined:
            for child in node.get('children') or []:
                visit(child)

    visit(payload)
    return result
