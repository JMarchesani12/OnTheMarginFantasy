"""Audit-only ingestion with real parser/SQL and canned fetch; external HTTP forbidden."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import date,datetime,timezone
import hashlib,time
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
import psycopg2
from sqlalchemy import create_engine,text,event
import measure_mod017 as base
from measure_mod017_transactions import verify_cleanup,save_json
from endpoints.schedule.ingestion_service import ScheduleIngestionService
from endpoints.schedule.helpers.espn.espnClient import ESPNClient

SIZES=(1,4,16)
DAY=date(2026,11,15)
WHEN=datetime(2026,11,15,18,tzinfo=timezone.utc)
TBD='api/migrations/20261030_game_kickoff_tbd.sql'


def payload(group,revision):
    events=[]
    for name in ({10:['A','B'],20:['A','C']}[group]):
        i=ord(name)-ord('A');home=2*i+1;away=home+1;corrected=revision==1 and name=='A'
        events.append(dict(id=name,date='2026-11-15T18:00:00Z',season={'type':2},competitions=[dict(timeValid=True,broadcast='Correction' if corrected else 'Audit',competitors=[dict(homeAway='home',team=dict(id=str(home),displayName=f'Team {home}'),score=str(99 if corrected else 80+i)),dict(homeAway='away',team=dict(id=str(away),displayName=f'Team {away}'),score=str(70+i))])]))
    if group==10:events.append(dict(id='ignored',date='2026-11-15T18:00:00Z',competitions=[]))
    return dict(events=events)


class Provider:
    def __init__(self):self.calls=[];self.revision=0;self.fail_once=False

class CannedClient(ESPNClient):
    def __init__(self,url,keyword,provider):super().__init__(url,keyword);self.provider=provider
    def fetch_scoreboard_for_date(self,datestr,group_id):
        self.provider.calls.append((datestr,group_id))
        if self.provider.fail_once and group_id==20:
            self.provider.fail_once=False;raise OSError('Synthetic one-shot provider failure')
        return deepcopy(payload(group_id,self.provider.revision))


def expected_games(revision):
    return [dict(sport=1,sportSeasonId=2026,seasonPhaseId=1,externalGameId=name,date=WHEN,timeTBD=False,homeTeamId=2*i+1,awayTeamId=2*i+2,homeScore=99 if revision==1 and i==0 else 80+i,awayScore=70+i,homeTeamExternalId=2*i+1,awayTeamExternalId=2*i+2,homeTeamName=f'Team {2*i+1}',awayTeamName=f'Team {2*i+2}',broadcast='Correction' if revision==1 and i==0 else 'Audit') for i,name in enumerate(['A','B','C'])]


def expected_counts(n,path,revisions):
    return dict(sql=(40*n if path=='league' else 29)*revisions,fetches=(2*n if path=='league' else 2)*revisions,upserts=(4*n if path=='league' else 3)*revisions)


def expected_roles(n,path,revisions):
    upserts=expected_counts(n,path,revisions)['upserts'];units=(n if path=='league' else 1)*revisions
    counts=dict(api=units,team_lookup=2*upserts,phases=upserts,fallback=upserts,season_ref=upserts,phase_ref=upserts,team_ref=2*upserts,upsert=upserts)
    counts.update(dict(league=units,season_context=units,subdivision=units) if path=='league' else dict(season=units))
    return counts


def classify(statement):
    sql=' '.join(statement.split())
    if sql.startswith('INSERT INTO "GameResult"'):return 'upsert'
    if 'FOR SHARE' in sql:
        for table,role in [('SportSeason','season_ref'),('SeasonPhase','phase_ref'),('SportTeam','team_ref')]:
            if f'FROM "{table}"' in sql:return role
    if 'SELECT "api-keyword"' in sql:return 'api'
    if 'FROM "SportTeam"' in sql and '"externalId"' in sql:return 'team_lookup'
    if 'FROM "SeasonPhase" sp LEFT JOIN' in sql:return 'phases'
    if 'FROM "SeasonPhase" sp WHERE' in sql:return 'fallback'
    if 'FROM "SportSeasonSubdivision"' in sql:return 'subdivision'
    if 'ss.id AS "sportSeasonId"' in sql:return 'season_context'
    if 'SELECT id, "sport", "seasonYear", settings' in sql:return 'league'
    if 'SELECT id, "sportId" FROM "SportSeason"' in sql:return 'season'
    raise AssertionError('Unclassified ingestion statement')


class Tracker:
    def __init__(self):self.enabled=False;self.reset()
    def reset(self):self.counts=Counter();self.examples={}
    def before(self,conn,cursor,statement,parameters,context,executemany):
        if self.enabled:
            role=classify(statement);self.counts[role]+=1;self.examples.setdefault(role,dict(sql=statement,parameters=parameters))


def seed(conn):
    facts=base.seed(conn,100);conn.exec_driver_sql((base.ROOT/TBD).read_text())
    for sql in [
      '''UPDATE "Sport" SET "api-keyword"='basketball/audit',"apiGroupIds"='[10,20]'::jsonb,"baseUrlName"='synthetic' WHERE id=1''',
      '''UPDATE "SportTeam" SET "externalId"=id::text''',
      '''UPDATE "League" SET status='In-Season' ''',
      '''INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (2026,1,2026,'2026-01-01','2026-12-31')''',
      '''INSERT INTO "SportSeasonSubdivision" (id,"sportSeasonId",code,name,"regularSeasonStart","regularSeasonEnd") VALUES (1,2026,'MAIN','Synthetic','2026-01-01','2026-12-31')''',
      '''INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name,"startDate","endDate",priority) VALUES (1,2026,'RegularSeason','Synthetic regular','2026-01-01','2027-01-01',1)''',
    ]:conn.exec_driver_sql(sql)
    conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit();return facts


def read_games(engine):
    with engine.connect() as conn:
        rows=[dict(r) for r in conn.execute(text('''SELECT id,sport,"sportSeasonId","seasonPhaseId","externalGameId",date,"timeTBD","homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName",broadcast FROM "GameResult" ORDER BY "externalGameId"''')).mappings()]
    ids={r['externalGameId']:r.pop('id') for r in rows};return rows,ids


def clear_games(engine):
    with engine.begin() as conn:conn.exec_driver_sql('DELETE FROM "GameResult"')


def service_for(engine,provider):
    return ScheduleIngestionService(engine,'https://synthetic.invalid',client_factory=lambda url,keyword:CannedClient(url,keyword,provider))


def sweep(service,n,path):
    results=[service.ingest_league_for_job(i,DAY) for i in range(1,n+1)] if path=='league' else [service.ingest_season_for_job(2026,DAY)]
    for summary in results:
        if summary['sportId']!=1 or summary['sportSeasonId']!=2026 or summary['date']!=str(DAY):raise AssertionError('Ingestion summary scope changed')
        if summary['eventsSeen']!=(5 if path=='league' else 3):raise AssertionError('Raw versus deduped event semantics changed')
        if path=='season' and summary['gamesUpserted']!=3:raise AssertionError('Season upsert summary changed')
    return results


def measure(engine,n,path,scenario):
    revisions=2 if scenario=='correction' else 1;wanted=expected_counts(n,path,revisions);wanted_roles=expected_roles(n,path,revisions);tracker=Tracker();event.listen(engine,'before_cursor_execute',tracker.before);samples=[];examples={};signature=None
    try:
        for iteration in range(6):
            clear_games(engine);provider=Provider();service=service_for(engine,provider);tracker.reset();elapsed=0;original_ids=None
            for revision in range(revisions):
                provider.revision=revision;tracker.enabled=True;start=time.perf_counter()
                try:sweep(service,n,path)
                finally:elapsed+=(time.perf_counter()-start)*1000;tracker.enabled=False
                rows,ids=read_games(engine);base.assert_equivalent(base.signature(expected_games(revision)),base.signature(rows))
                if original_ids is None:original_ids=ids
                elif ids!=original_ids:raise AssertionError('Correction replaced game identities')
            if dict(tracker.counts)!=wanted_roles or len(provider.calls)!=wanted['fetches'] or sum(tracker.counts.values())!=wanted['sql']:raise AssertionError('Ingestion count formula mismatch')
            signature=base.signature(rows);examples.update(tracker.examples)
            if iteration:samples.append(dict(service_ms=elapsed,sql_count=sum(tracker.counts.values()),fetches=len(provider.calls),upserts=tracker.counts['upsert'],roles=dict(tracker.counts),provider_calls=list(provider.calls)))
        return dict(path=path,scenario=scenario,league_count=n,expected_counts=wanted,expected_roles=wanted_roles,result=signature,samples=samples,median_service_ms=base.statistics.median(s['service_ms'] for s in samples),statement_examples=examples,invocations=6,correction_ids_preserved=original_ids is not None if revisions==2 else None)
    finally:tracker.enabled=False;event.remove(engine,'before_cursor_execute',tracker.before)


def failure_probe(engine,path):
    clear_games(engine);provider=Provider();provider.fail_once=True;service=service_for(engine,provider);tracker=Tracker();event.listen(engine,'before_cursor_execute',tracker.before);caught=None
    try:
        tracker.enabled=True
        try:sweep(service,2,path)
        except (OSError,RuntimeError) as error:caught=type(error).__name__
        finally:tracker.enabled=False
        if caught!=('OSError' if path=='league' else 'RuntimeError'):raise AssertionError('Expected group failure missing')
        partial,_=read_games(engine);base.assert_equivalent(base.signature(expected_games(0)[:2]),base.signature(partial))
        tracker.enabled=True
        try:sweep(service,2,path)
        finally:tracker.enabled=False
        rows,_=read_games(engine);base.assert_equivalent(base.signature(expected_games(0)),base.signature(rows))
        wanted=dict(sql=102,fetches=6,upserts=10) if path=='league' else dict(sql=49,fetches=4,upserts=5)
        actual=dict(sql=sum(tracker.counts.values()),fetches=len(provider.calls),upserts=tracker.counts['upsert'])
        if actual!=wanted:raise AssertionError('Failure/rerun counts changed')
        return dict(path=path,error_type=caught,partial_rows=2,final_rows=3,expected_counts=wanted,actual_counts=actual,partial_result=base.signature(partial),final_result=base.signature(rows),automatic_retry=False)
    finally:tracker.enabled=False;event.remove(engine,'before_cursor_execute',tracker.before)


def run_tier(admin,n,report):
    record=None
    try:
        with base.owned_database(admin) as database:
            record=dict(name=database,cleanup='pending');report['databases'].append(record)
            engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=database,**base.LOCAL))
            try:
                with patch('requests.sessions.Session.request',side_effect=AssertionError('HTTP forbidden in ingestion audit')):
                    with engine.connect() as conn:
                        base.schema(conn);facts=seed(conn);settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','shared_buffers','work_mem','statement_timeout','lock_timeout']}
                    measurements=[measure(engine,n,path,scenario) for path in ['league','season'] for scenario in ['overlap','correction']]
                    probes=[failure_probe(engine,path) for path in ['league','season']] if n==16 else []
                    return dict(league_count=n,fixture=facts,settings=settings,measurements=measurements,failure_probes=probes)
            finally:engine.dispose()
    finally:
        if record is not None:verify_cleanup(admin,record)


def run(directory,manifest,tiers,connect=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);run_id=uuid4().hex;artifact=directory/f'mod-022-ingestion-{run_id}.json'
    inputs=[base.BASELINE,*base.MIGRATIONS,TBD,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod022_ingestion.py','api/endpoints/schedule/ingestion_service.py','api/endpoints/schedule/ingestion_repository.py','api/endpoints/schedule/calendar_service.py','api/endpoints/schedule/calendar_repository.py','api/endpoints/schedule/helpers/espn/espnClient.py','api/rules/tournamentRules.py','api/utils/conference_membership.py','api/cronJobs/cronIngestScoreboard.py']
    report=dict(date='2026-11-15',run_id=run_id,started_at=datetime.now(timezone.utc).isoformat(),result='RUNNING',scope='Synthetic ingestion orchestration/canned-provider measurements only; optimization deferred',tiers=[],databases=[],cleanup='no database created',provenance={},limits=['Canned transport only,actual parser/service/SQL; no external HTTP/cron/checkpoints','Same sport/year/date,identical cross-group duplicates; conflicting payload precedence unmeasured','Real committed upserts in owned synthetic DBs,not production/network/provider/retry-policy performance'])
    def persist():
        save_json(artifact,report);save_json(Path(manifest),dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        report['provenance']={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in inputs}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        for n in tiers:
            print(f'MOD022 ingestion leagues {n}: starting',flush=True);report['tiers'].append(run_tier(admin,n,report));persist();print(f'MOD022 ingestion leagues {n}: PASS',flush=True)
        if len(report['databases'])!=len(tiers) or any(r['cleanup']!='removed' for r in report['databases']):raise RuntimeError('Owned cleanup not verified')
        report['cleanup']='verified';report['result']='PASS';return report
    except BaseException as error:
        report['result']='FAILED';report['error_type']=type(error).__name__
        if report['databases']:report['cleanup']='verified' if all(r['cleanup']=='removed' for r in report['databases']) else 'incomplete or unverified'
        raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();persist()
        if admin is not None:admin.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tier',type=int,choices=SIZES,action='append');args=parser.parse_args()
    directory=base.ROOT/'docs/modernization/evidence';run(directory,directory/'mod-022-ingestion-current-2026-11-15.json',args.tier or SIZES)
if __name__=='__main__':main()
