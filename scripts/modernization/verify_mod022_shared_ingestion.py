"""Shared live-ingestion policy on owned marked PostgreSQL; real HTTP forbidden."""
from copy import deepcopy
from datetime import datetime,timezone
from uuid import uuid4
from unittest.mock import patch
import hashlib
import io
from contextlib import redirect_stderr
import psycopg2
from sqlalchemy import create_engine,event,text
import measure_mod017 as base
import measure_mod022_ingestion as fixture
from measure_mod017_transactions import save_json,verify_cleanup
from endpoints.schedule.ingestion_service import ScheduleIngestionService
from endpoints.schedule.shared_ingestion_service import SharedScoreboardIngestionService
from endpoints.schedule.helpers.espn.espnClient import ESPNClient
from cronJobs import cronIngestScoreboard as cron

class Provider:
    def __init__(self,mode='overlap'):self.mode=mode;self.calls=[];self.fail_once=False

class Client(ESPNClient):
    def __init__(self,url,keyword,provider):super().__init__(url,keyword);self.provider=provider
    def fetch_scoreboard_for_date(self,datestr,group_id):
        self.provider.calls.append((self.api_keyword,datestr,group_id))
        if self.provider.fail_once and group_id==20:self.provider.fail_once=False;raise OSError('Synthetic private fetch failure')
        revision=1 if group_id==20 and self.provider.mode in ('later','revert') else 0
        payload=fixture.payload(10 if group_id==30 else group_id,revision)
        if group_id==30:payload['events']=payload['events'][:1]
        if self.provider.mode in ('phase','conference') and group_id==20:payload['events'][0]['notes']=[dict(headline='Special')]
        if self.provider.mode=='missing' and group_id==10:
            missing=deepcopy(payload['events'][0]);missing['id']='';payload['events'].append(missing)
        if self.provider.mode=='unmapped':
            for game in payload['events']:
                if game.get('id')=='A':game['competitions'][0]['competitors'][0]['team']['id']='999'
        return deepcopy(payload)

def service_for(engine,provider):return ScheduleIngestionService(engine,'https://synthetic.invalid',client_factory=lambda u,k:Client(u,k,provider))
def outcomes(service,ids,day=fixture.DAY):return list(SharedScoreboardIngestionService(service,lambda:None).iter_league_outcomes(ids,day))
def safe_rows(rows):return [dict(leagueId=r['leagueId'],date=r['date'],summary=r['summary'],error=type(r['error']).__name__ if r['error'] else None) for r in rows]

def reset(engine):
    fixture.clear_games(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql('DELETE FROM "SeasonPhase" WHERE id=99; DELETE FROM "TournamentDefinition" WHERE id=99; DELETE FROM "ConferenceMembership" WHERE "sportConferenceId"=99; DELETE FROM "SportConference" WHERE id=99; DELETE FROM "Conference" WHERE id=99')
        conn.exec_driver_sql('UPDATE "Sport" SET "apiGroupIds"=\'[10,20]\'::jsonb WHERE id=1')

def conflict_cases(engine):
    records=[]
    for mode in ('overlap','later','revert','duplicates','missing','unmapped','phase','override','conference'):
        reset(engine);provider=Provider(mode);service=service_for(engine,provider);writes=[]
        if mode in ('revert','duplicates'):
            with engine.begin() as conn:conn.execute(text('UPDATE "Sport" SET "apiGroupIds"=CAST(:groups AS jsonb) WHERE id=1'),dict(groups='[10,20,30]' if mode=='revert' else '[10,10,20]'))
        if mode in ('phase','override','conference'):
            with engine.begin() as conn:
                if mode=='conference':
                    conn.exec_driver_sql('''INSERT INTO "Conference" (id,name) VALUES (99,'Synthetic'); INSERT INTO "SportConference" (id,"conferenceId","sportId","maxTeamsPerOwner") VALUES (99,99,1,4);
                    INSERT INTO "ConferenceMembership" ("sportTeamId","sportConferenceId","seasonYear","sportId") VALUES (1,99,2026,1),(2,99,2026,1);
                    INSERT INTO "TournamentDefinition" (id,"sportId",code,name,scope,"sportConferenceId") VALUES (99,1,'SYNTHETIC','Synthetic','conference',99)''')
                conn.execute(text('''INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name,"startDate","endDate",priority,rules,"tournamentId") VALUES (99,2026,:type,'Special','2026-01-01','2027-01-01',2,CAST(:rules AS jsonb),:tournament)'''),dict(type='ConferenceTournament' if mode=='conference' else 'NationalTournament',rules='{"eventIds":["A"]}' if mode=='override' else '{"sourceLabels":["Special"]}',tournament=99 if mode=='conference' else None))
                # In conference mode unlabeled A would be rejected in its known
                # window; label both copies to test mapped conference selection.
        if mode=='conference':
            original=service._new_client
            def client_with_labels(*a):
                client=original(*a);fetch=client.fetch_scoreboard_for_date
                def fetch_labeled(*args):
                    payload=fetch(*args)
                    for row in payload['events']:
                        if row.get('id')=='A':row['notes']=[dict(headline='Special')]
                    return payload
                client.fetch_scoreboard_for_date=fetch_labeled;return client
            service._new_client=client_with_labels
        def count(conn,cursor,statement,params,context,many):
            if statement.lstrip().startswith('INSERT INTO "GameResult"'):writes.append(params)
        event.listen(engine,'after_cursor_execute',count)
        try:result=outcomes(service,[1,2,3])
        finally:event.remove(engine,'after_cursor_execute',count)
        assert all(r['error'] is None for r in result),(mode,safe_rows(result))
        rows,ids=fixture.read_games(engine);wanted=fixture.expected_games(1 if mode=='later' else 0)
        if mode=='unmapped':wanted[0].update(homeTeamId=None,homeTeamExternalId=999)
        if mode in ('phase','override','conference'):wanted[0]['seasonPhaseId']=99
        base.assert_equivalent(base.signature(wanted),base.signature(rows))
        expected_writes=5 if mode=='revert' else 4 if mode in ('later','phase') else 3
        assert len(writes)==expected_writes,(mode,len(writes))
        assert len(provider.calls)==(3 if mode=='revert' else 2)
        assert all(r['summary']['eventsSeen']==(6 if mode in ('revert','missing') else 5) for r in result)
        records.append(dict(mode=mode,fetches=len(provider.calls),upserts=len(writes),outcomes=safe_rows(result),stored=base.signature(rows)))
    return records

def add_other_units(engine):
    reset(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql('''INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (2027,1,2027,'2026-01-01','2026-12-31');
        INSERT INTO "SportSeasonSubdivision" (id,"sportSeasonId",code,name,"regularSeasonStart","regularSeasonEnd") VALUES (2,2027,'MAIN','Other','2026-01-01','2026-12-31');
        INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name,"startDate","endDate",priority) VALUES (2,2027,'RegularSeason','Other','2026-01-01','2027-01-01',1);
        UPDATE "League" SET "seasonYear"=2027 WHERE id=20;
        INSERT INTO "Sport" (id,name,"maxPlayersToHaveMaxRounds","maxDraftRounds","api-keyword","apiGroupIds") VALUES (2,'Other',8,4,'other/audit','[10,20]'::jsonb);
        INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (3026,2,2026,'2026-01-01','2026-12-31');
        INSERT INTO "SportSeasonSubdivision" (id,"sportSeasonId",code,name,"regularSeasonStart","regularSeasonEnd") VALUES (3,3026,'MAIN','Other sport','2026-01-01','2026-12-31');
        INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name,"startDate","endDate",priority) VALUES (3,3026,'RegularSeason','Other sport','2026-01-01','2027-01-01',1);
        INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName",tier,"externalId") SELECT 100+id,"schoolId",2,"displayName",1,"externalId" FROM "SportTeam" WHERE id<=6;
        UPDATE "League" SET sport=2 WHERE id=30''')


def failure_and_isolation(engine):
    records=[];add_other_units(engine)
    for kind in ('fetch','reference','commit'):
        fixture.clear_games(engine);provider=Provider();provider.fail_once=kind=='fetch';service=service_for(engine,provider)
        original=service._lookup_season_phase_id_for_game
        if kind=='reference':service._lookup_season_phase_id_for_game=lambda season,when,**kw:99999 if season==2026 and kw['game']['externalGameId']=='B' else original(season,when,**kw)
        if kind=='commit':
            with engine.begin() as conn:conn.exec_driver_sql('''CREATE FUNCTION mod022_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW."sportSeasonId"=2026 AND NEW."externalGameId"='B' THEN RAISE EXCEPTION 'synthetic commit'; END IF; RETURN NEW; END $$;
            CREATE CONSTRAINT TRIGGER mod022_fail AFTER INSERT OR UPDATE ON "GameResult" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mod022_fail();''')
        try:
            result=outcomes(service,[1,20,2,30,9999])
            assert [r['error'] is not None for r in result]==[True,False,True,False,True]
            with engine.connect() as conn:
                partial=[dict(r) for r in conn.exec_driver_sql('SELECT id,"externalGameId" FROM "GameResult" WHERE "sportSeasonId"=2026 ORDER BY "externalGameId"').mappings()]
            assert [r['externalGameId'] for r in partial]==(['A','B'] if kind=='fetch' else ['A'])
        finally:
            if kind=='commit':
                with engine.begin() as conn:conn.exec_driver_sql('DROP TRIGGER mod022_fail ON "GameResult"; DROP FUNCTION mod022_fail()')
        retry=outcomes(service_for(engine,provider),[1,2]);assert all(r['error'] is None for r in retry)
        with engine.connect() as conn:
            after={r['externalGameId']:r['id'] for r in conn.exec_driver_sql('SELECT id,"externalGameId" FROM "GameResult" WHERE "sportSeasonId"=2026').mappings()}
            assert len(after)==3 and all(after[r['externalGameId']]==r['id'] for r in partial)
            scopes=dict(conn.exec_driver_sql('SELECT "sportSeasonId",COUNT(*) FROM "GameResult" GROUP BY "sportSeasonId"').all());assert scopes=={2026:3,2027:3,3026:3}
            for season,phase,sport in [(2026,1,1),(2027,2,1),(3026,3,2)]:
                rows=[dict(r) for r in conn.execute(text('SELECT sport,"sportSeasonId","seasonPhaseId","externalGameId",date,"timeTBD","homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName",broadcast FROM "GameResult" WHERE "sportSeasonId"=:season ORDER BY "externalGameId"'),dict(season=season)).mappings()]
                wanted=deepcopy(fixture.expected_games(0))
                for row in wanted:
                    row.update(sport=sport,sportSeasonId=season,seasonPhaseId=phase)
                    if sport==2:row['homeTeamId']+=100;row['awayTeamId']+=100
                base.assert_equivalent(base.signature(wanted),base.signature(rows))
        records.append(dict(kind=kind,outcomes=safe_rows(result),partial=partial,final_scopes=scopes,new_invocation_retry=True,ids_preserved=True,fetches_total=len(provider.calls)))
    # Different dates create new units even on the same coordinator.
    provider=Provider();service=service_for(engine,provider);shared=SharedScoreboardIngestionService(service,lambda:None)
    for day in (fixture.DAY,fixture.DAY.replace(day=16)):assert all(r['error'] is None for r in shared.iter_league_outcomes([1,2],day))
    assert len(provider.calls)==4
    return dict(cases=records,date_isolation_fetches=4)


def actual_cron(engine):
    reset(engine)
    provider=Provider();service=service_for(engine,provider)
    active=service.active_leagues_for_job(fixture.DAY);selected=active[:16]
    service.active_leagues_for_job=lambda day:selected
    fixed=datetime(2026,11,15,3,tzinfo=cron.ZoneInfo('America/Chicago'))
    class Clock(datetime):
        @classmethod
        def now(cls,tz=None):return fixed.astimezone(tz) if tz else fixed
    logs=io.StringIO()
    with patch.object(cron,'ScheduleIngestionService',return_value=service),patch.object(cron.dt,'datetime',Clock),redirect_stderr(logs):report=cron.main(engine=engine)
    assert report==dict(processed=[dict(leagueId=i,date=str(fixture.DAY)) for i in selected],failures=[])
    assert len(provider.calls)==2
    return dict(report=report,fetches=2,active_query_rows=len(active),bounded_selection=len(selected),real_advisory_gate=True,scope='Actual main/engine/gate, fixed clock, selection bounded to first16 actual eligible IDs, canned transport')


def run():
    directory=base.ROOT/'docs/modernization/evidence';run_id=uuid4().hex;artifact=directory/f'mod-022-shared-{run_id}.json';manifest=directory/'mod-022-shared-current-2026-11-16.json'
    report=dict(run_id=run_id,result='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),provenance={},databases=[],cleanup='no database created')
    def persist():save_json(artifact,report);save_json(manifest,dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        files=[base.BASELINE,*base.MIGRATIONS,fixture.TBD,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod022_ingestion.py','scripts/modernization/verify_mod022_shared_ingestion.py','api/endpoints/schedule/shared_ingestion_service.py','api/endpoints/schedule/ingestion_service.py','api/endpoints/schedule/ingestion_repository.py','api/endpoints/schedule/calendar_service.py','api/endpoints/schedule/calendar_repository.py','api/endpoints/schedule/helpers/espn/espnClient.py','api/rules/tournamentRules.py','api/utils/conference_membership.py','api/cronJobs/cronIngestScoreboard.py','api/operations.py']
        report['provenance']={f:hashlib.sha256((base.ROOT/f).read_bytes()).hexdigest() for f in files}
        admin=psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        try:
            with base.owned_database(admin) as name:
                record=dict(name=name,cleanup='pending');report['databases'].append(record);persist()
                engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
                try:
                    with patch('requests.sessions.Session.request',side_effect=AssertionError('Real HTTP forbidden')):
                        with engine.connect() as conn:base.schema(conn);report['fixture']=fixture.seed(conn)
                        report['conflicts']=conflict_cases(engine);report['cron']=actual_cron(engine);report['failure_isolation']=failure_and_isolation(engine)
                finally:engine.dispose()
        finally:
            for record in report['databases']:verify_cleanup(admin,record)
            report['cleanup']='verified' if report['databases'] and all(r['cleanup']=='removed' for r in report['databases']) else 'unverified'
        assert report['cleanup']=='verified';report['result']='PASS';return report
    except BaseException as error:report['result']='FAILED';report['error_type']=type(error).__name__;report['error']=str(error);raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();persist()
        if admin is not None:admin.close()
        print(artifact.name,report['result'],report['cleanup'],flush=True)
if __name__=='__main__':run()
