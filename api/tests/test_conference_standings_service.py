import datetime as dt
import unittest
from contextlib import nullcontext
from endpoints.scoring.standings_service import ConferenceStandingsService
from endpoints.scoring.standings_provider import ESPNStandingsProvider
import test_conference_standings_provider as provider_fixture

class Store:
    def lock_for_collection(self,*args): return True
    def __init__(self): self.rows=[]
    def season(self,conn,season_id):
        return {'id':season_id,'sportId':2,'apiKeyword':'football/college-football','regularEnd':'2025-12-12'}
    def teams(self,conn,season_id):
        payload=provider_fixture.StandingsProviderTests().payload()
        return [{'sportTeamId':int(e['team']['id']), 'externalId':e['team']['id'], 'sportConferenceId':7}
                for e in payload['children'][0]['standings']['entries']]
    def save(self,conn,values):
        if not any(r['digest']==values['digest'] for r in self.rows): self.rows.append(values)
        return 1

class Engine:
    def begin(self): return nullcontext(object())

class Provider:
    def fetch(self,keyword,year,group):
        data=provider_fixture.StandingsProviderTests().payload()
        if group==81: return {'id':'81','season':{'year':year},'children':[]}
        return data

class StandingsCollectionTests(unittest.TestCase):
    def setUp(self):
        self.store=Store();self.service=ConferenceStandingsService(Engine(),Provider(),self.store)

    def test_preview_does_not_write_and_apply_replays_converge(self):
        now=dt.datetime(2025,12,13,tzinfo=dt.timezone.utc)
        report=self.service.collect_for_job(1,now=now)
        self.assertEqual(report['ready'],[7]);self.assertEqual(self.store.rows,[])
        for _ in range(2): self.service.collect_for_job(1,apply=True,now=now)
        self.assertEqual(len(self.store.rows),1)
        self.assertTrue(self.store.rows[0]['isFinal'])
        self.assertEqual(next(e for e in self.store.rows[0]['entries'] if e['sportTeamId']==2641)['rank'],1)

    def test_during_regular_season_is_provisional(self):
        self.service.collect_for_job(1,apply=True,now=dt.datetime(2025,11,1,tzinfo=dt.timezone.utc))
        self.assertFalse(self.store.rows[0]['isFinal'])

    def test_membership_mismatch_never_saves_partial_conference(self):
        original=self.store.teams
        self.store.teams=lambda conn,season: original(conn,season)[:-1]
        report=self.service.collect_for_job(1,apply=True)
        self.assertEqual(self.store.rows,[]);self.assertEqual(report['pending'],[7])

    def test_provider_error_keeps_previous_good_snapshot(self):
        self.service.collect_for_job(1,apply=True)
        before=list(self.store.rows)
        def fail(*args): raise RuntimeError('provider failure')
        self.service.provider.fetch=fail
        with self.assertRaises(RuntimeError): self.service.collect_for_job(1,apply=True)
        self.assertEqual(self.store.rows,before)

    def test_no_regular_season_boundary_is_rejected(self):
        original=self.store.season
        self.store.season=lambda conn,season: {**original(conn,season),'regularEnd':None}
        with self.assertRaises(ValueError): self.service.collect_for_job(1,apply=True)
        self.assertEqual(self.store.rows,[])

class StandingsJobTests(unittest.TestCase):
    def test_ingestion_collects_standings_and_reports_failure_safely(self):
        from unittest.mock import patch
        from test_operational_jobs import fake_gate
        from cronJobs import cronIngestScoreboard as job
        with patch.object(job,'job_gate',fake_gate), patch.object(job,'ScheduleIngestionService') as games, patch.object(job,'ConferenceStandingsService') as standings:
            games.return_value.active_leagues_for_job.return_value=[]
            standings.return_value.collect_active_for_job.return_value={'processed':[], 'failures':[{'sportSeasonId':1,'category':'Timeout'}]}
            report=job.main(engine=object())
            self.assertEqual(report['failures'],[{'sportSeasonId':1,'category':'Timeout'}])
            standings.return_value.collect_active_for_job.assert_called_once()

class CollectionRaceTests(unittest.TestCase):
    def test_changed_membership_between_fetch_and_apply_is_not_committed(self):
        store=Store();initial=store.teams
        calls=[]
        def teams(conn,season):
            calls.append(1)
            return initial(conn,season) if len(calls)==1 else initial(conn,season)[:-1]
        store.teams=teams
        store.lock_for_collection=lambda *args:True
        with self.assertRaises(ValueError): ConferenceStandingsService(Engine(),Provider(),store).collect_for_job(1,apply=True)
        self.assertEqual(store.rows,[])

    def test_changed_season_cutoff_between_fetch_and_apply_is_not_committed(self):
        store=Store();original=store.season;calls=[]
        def season(conn,season_id):
            calls.append(1)
            return {**original(conn,season_id),'regularEnd':'2025-12-12' if len(calls)==1 else '2027-01-01'}
        store.season=season
        with self.assertRaises(ValueError): ConferenceStandingsService(Engine(),Provider(),store).collect_for_job(1,apply=True)
        self.assertEqual(store.rows,[])

    def test_duplicate_external_team_identity_is_rejected(self):
        store=Store();original=store.teams
        store.teams=lambda *args:original(*args)+[{**original(*args)[0],'sportTeamId':99999}]
        with self.assertRaises(ValueError): ConferenceStandingsService(Engine(),Provider(),store).collect_for_job(1,apply=True)
        self.assertEqual(store.rows,[])

class SnapshotFreshnessTests(unittest.TestCase):
    def test_corrected_regular_season_boundary_invalidates_old_final_snapshot(self):
        from test_league_read_authorization import ReadDatabase
        from endpoints.scoring.standings_repository import ConferenceStandingsRepository
        db=ReadDatabase();self.addCleanup(db.connection.close)
        db.connection.executescript('''CREATE TABLE ConferenceStandingsSnapshot(id INTEGER,sportSeasonId INTEGER,sportConferenceId INTEGER,isFinal BOOLEAN,regularEnd TEXT);
            INSERT INTO ConferenceStandingsSnapshot VALUES(1,1,7,true,'2025-12-12');
            CREATE TABLE SportSeasonSubdivision(sportSeasonId INTEGER,regularSeasonEnd TEXT);
            INSERT INTO SportSeasonSubdivision VALUES(1,'2025-12-12');''')
        repo=ConferenceStandingsRepository()
        self.assertEqual(len(repo.latest_validated(db,1)),1)
        db.connection.execute("UPDATE SportSeasonSubdivision SET regularSeasonEnd='2025-12-14'")
        self.assertEqual(repo.latest_validated(db,1),[])
