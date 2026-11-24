"""Automatic standings collection. Provider I/O precedes write transactions."""
from datetime import datetime, timezone, date
import hashlib
import json
from .standings_provider import ESPNStandingsProvider, parse_conference_standings, provider_year, BASE_URL
from .standings_repository import ConferenceStandingsRepository


class ConferenceStandingsService:
    def __init__(self, engine, provider=None, repository=None):
        self.engine = engine
        self.provider = provider or ESPNStandingsProvider()
        self.repository = repository or ConferenceStandingsRepository()

    def collect_for_job(self, sport_season_id, *, apply=False, now=None):
        now = now or datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            season = self.repository.season(conn, sport_season_id)
            teams = self.repository.teams(conn, sport_season_id)
        if not season or not season['regularEnd']:
            raise ValueError('A configured regular-season end is required')
        regular_end = date.fromisoformat(str(season['regularEnd'])[:10])
        year = provider_year(season['apiKeyword'], regular_end)
        groups = (80,81) if season['apiKeyword']=='football/college-football' else (50,)
        conferences = []
        for group in groups:
            payload = self.provider.fetch(season['apiKeyword'], year, group)
            for conf in parse_conference_standings(payload, year, group):
                conf['group'] = group
                conferences.append(conf)
        expected = {}
        seen_teams = set()
        seen_external_ids = set()
        for team in teams:
            identity = int(team['sportTeamId'])
            external_id = str(team['externalId'])
            if identity in seen_teams or external_id in seen_external_ids:
                raise ValueError('Ambiguous season conference membership')
            seen_teams.add(identity)
            seen_external_ids.add(external_id)
            expected.setdefault(int(team['sportConferenceId']), {})[str(team['externalId'])] = int(team['sportTeamId'])
        report = {'sportSeasonId': sport_season_id, 'ready': [], 'pending': [], 'applied': apply}
        accepted = []
        for conference_id, mapping in expected.items():
            candidates = [c for c in conferences if c['status']=='ready'
                          and {e['externalId'] for e in c['entries']}==set(mapping)]
            if len(candidates)!=1:
                report['pending'].append(conference_id)
                continue
            conf = candidates[0]
            entries = sorted([{**entry,'sportTeamId':mapping[entry['externalId']]} for entry in conf['entries']], key=lambda e:e['sportTeamId'])
            values = {'sportSeasonId':sport_season_id,'sportConferenceId':conference_id,'sourceYear':year,
                      'sourceUrl':f"{BASE_URL}/{season['apiKeyword']}/standings?season={year}&seasontype=2&level=3&group={conf['group']}",
                      'regularEnd':regular_end,'isFinal':now.date()>regular_end,'entries':entries}
            values['digest'] = hashlib.sha256(json.dumps(values,sort_keys=True,default=str).encode()).hexdigest()
            accepted.append(values)
            report['ready'].append(conference_id)
        if apply:
            with self.engine.begin() as conn:
                if not self.repository.lock_for_collection(conn,sport_season_id):
                    return {**report,'applied':False,'skipped':'season_finalized'}
                current_season=self.repository.season(conn,sport_season_id)
                source_context=lambda value: (value['sportId'],value['apiKeyword'],str(value['regularEnd'])) if value else None
                if source_context(current_season)!=source_context(season):
                    raise ValueError('Standings source or season dates changed during collection')
                current=self.repository.teams(conn,sport_season_id)
                identity=lambda rows: sorted((int(t['sportTeamId']),str(t['externalId']),int(t['sportConferenceId'])) for t in rows)
                if identity(current)!=identity(teams):
                    raise ValueError('Season conference membership changed during collection')
                for values in accepted:
                    self.repository.save(conn, values)
        return report

    def collect_active_for_job(self, *, now=None):
        now = now or datetime.now(timezone.utc)
        with self.engine.begin() as conn:
            seasons = self.repository.eligible_seasons(conn,now.date())
        report = {'processed': [], 'failures': []}
        for season_id in seasons:
            try:
                report['processed'].append(self.collect_for_job(season_id,apply=True,now=now))
            except Exception as exc:
                report['failures'].append({'sportSeasonId':season_id,'category':type(exc).__name__})
        return report
