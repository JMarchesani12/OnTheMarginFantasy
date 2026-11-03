"""Trusted ingestion, provider failures and checkpoint behavior without network."""
import datetime as dt
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock


class Provider:
    def __init__(self):
        self.calls = []
        self.failure = None
    def fetch_scoreboard_for_date(self, datestr, group_id):
        self.calls.append((datestr,group_id))
        if group_id == self.failure: raise OSError('synthetic provider failure')
        return [{'externalGameId':'event'},None,{'externalGameId':''}]
    def iter_scoreboard_events(self, payload): return iter(payload)
    def extract_game_from_event(self, event): return event
    def fetch_team_schedule(self, team):
        if team == 'bad': raise OSError('synthetic team failure')
        return [{'externalGameId':'event'}]


class ScheduleIngestionTests(unittest.TestCase):
    def service(self):
        from endpoints.schedule.ingestion_service import ScheduleIngestionService
        engine = MagicMock();engine.url = 'postgresql://synthetic/checkpoint-test'
        row = dict(id=1,sportId=1,scheduleBootstrapped=False,
                   seasonStart=dt.date(2027,3,1),seasonEnd=dt.date(2027,3,3))
        result = SimpleNamespace(mappings=lambda:SimpleNamespace(first=lambda:row))
        marks = []
        repo = SimpleNamespace(season_for_ingestion=lambda conn,params:result,
            season_for_bootstrap=lambda conn,params:result,
            bootstrap_start=lambda conn,params:marks.append(False),
            bootstrap_finish=lambda conn,params:marks.append(params['complete']),
            mark_team_bootstrapped=lambda conn,params:marks.append(True))
        provider = Provider();factories = []
        def factory(url, keyword):
            factories.append((url,keyword));return provider
        service = ScheduleIngestionService(engine,'https://provider.example.test///',repository=repo,client_factory=factory)
        service._get_sport_api_config = lambda _: ('basketball',[50,55],'basketball')
        service._get_season_phases = lambda _: []
        service._get_league = lambda _: {'sport':1}
        service._get_sport_season_for_league = lambda _: {'sportSeasonId':1}
        writes = []
        service._insert_or_update_game = lambda sport,season,game:writes.append(game['externalGameId'])
        return service,provider,writes,marks,factories,row

    def test_scoreboard_dedupes_groups_and_constructs_provider_only_at_operation(self):
        service,provider,writes,_,factories,_ = self.service()
        self.assertEqual(factories,[])
        result = service.ingest_season_for_job(1,dt.date(2027,3,1))
        self.assertEqual((result['eventsSeen'],result['gamesUpserted'],writes),(1,1,['event']))
        self.assertEqual(provider.calls,[('20270301',50),('20270301',55)])
        self.assertEqual(factories,[('https://provider.example.test','basketball')])

    def test_fetch_failure_preserves_already_completed_game_and_error_context(self):
        service,provider,writes,_,_,_ = self.service();provider.failure = 55
        with self.assertRaisesRegex(RuntimeError,'sport=1, date=20270301, group=55'):
            service.ingest_season_for_job(1,dt.date(2027,3,1))
        self.assertEqual(writes,['event'])

    def test_league_ingestion_retains_event_count_and_non_deduped_behavior(self):
        service,_,writes,_,_,_ = self.service()
        result = service.ingest_league_for_job(10,dt.date(2027,3,1))
        self.assertEqual(result['eventsSeen'],6)
        self.assertEqual(writes,['event','','event',''])

    def test_team_bootstrap_retains_skip_failure_and_completion_behavior(self):
        service,_,writes,marks,_,_ = self.service()
        service._get_all_sport_teams = lambda *args,**kwargs:[{'externalId':'good'},{'externalId':'bad'}]
        result = service.bootstrap_teams_for_job(1,1)
        self.assertEqual((result['teamsProcessed'],writes,marks),(2,['event'],[True]))

    def test_canonical_checkpoint_partial_resume_force_and_validation(self):
        service,_,_,marks,_,_ = self.service();days = []
        service.ingest_scoreboard_for_date_for_sport_season = lambda season,day:(days.append(day) or {'eventsSeen':0,'gamesUpserted':0})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'progress.json'
            partial = service.bootstrap_for_job(1,max_days=1,checkpoint_path=path)
            self.assertFalse(partial['complete'])
            complete = service.bootstrap_for_job(1,checkpoint_path=path)
            self.assertEqual((complete['daysSkipped'],complete['daysProcessed'],complete['complete']),(1,2,True))
            days.clear();service.bootstrap_for_job(1,force=True,checkpoint_path=path)
            self.assertEqual(len(days),3)
            with self.assertRaisesRegex(ValueError,'max_days'):
                service.bootstrap_for_job(1,max_days=True,checkpoint_path=path)
        self.assertEqual(marks[:4],[False,False,False,True])

    def test_failed_dates_retried_and_successes_skipped(self):
        service,_,_,_,_,_ = self.service();days = []
        def failed(season,day):
            days.append(day)
            if day.day==2: raise ValueError('synthetic date failure')
            return {}
        service.ingest_scoreboard_for_date_for_sport_season = failed
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'checkpoint.json'
            self.assertFalse(service.bootstrap_for_job(1,checkpoint_path=path)['complete'])
            days.clear()
            service.ingest_scoreboard_for_date_for_sport_season = lambda season,day:(days.append(day) or {})
            self.assertTrue(service.bootstrap_for_job(1,checkpoint_path=path)['complete'])
            self.assertEqual([day.day for day in days],[2])

    def test_api_groups_and_supplied_connection_upsert_preserve_protocol(self):
        from endpoints.schedule.ingestion_service import ScheduleIngestionService
        for raw in (None,[50,'55'],'[50,55]','50, 55',(50,55)):
            engine = MagicMock();engine.begin.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = ('basketball',raw,'basketball')
            service = ScheduleIngestionService(engine,'')
            self.assertEqual(service._get_sport_api_config(1)[1],[] if raw is None else [50,55])
        engine = MagicMock();conn = MagicMock();conn.execute.return_value.fetchone.return_value = (9,)
        service = ScheduleIngestionService(engine,'')
        self.assertEqual(service.upsert_season_for_job(conn,1,2027,dt.date(2027,1,1),dt.date(2027,2,1)),9)
        engine.begin.assert_not_called()
