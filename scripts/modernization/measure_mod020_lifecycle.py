"""Version2 explicit authorized scoped lifecycle reads on marked localhost; frozen v1 raw unchanged."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
import hashlib,time
from pathlib import Path
from uuid import uuid4
import psycopg2
from sqlalchemy import create_engine,text,event
import measure_mod017 as base
from measure_mod017_transactions import verify_cleanup,save_json
from endpoints.league.lifecycle.service import LeagueLifecycleService
from endpoints.league.lifecycle.query_service import LeagueLifecycleQueryService
from actors import UserActor

SIZES=base.SIZES
CALLS=('detail','denied','missing','mine')
PHASES={'Pre-Draft':'pre','Drafting':'drafting','Post-Draft':'post','In-Season':'in_season','Completed':'completed'}
INITIAL=['In-Season','Pre-Draft','Pre-Draft','Pre-Draft','Pre-Draft','In-Season','Completed','Completed','In-Season','Post-Draft']
FINAL=['Pre-Draft','Drafting','Drafting','Post-Draft','In-Season','Completed','Completed','Completed','In-Season','Pre-Draft']
EPOCH=datetime(2000,1,1,tzinfo=timezone.utc)


def initial_status(league):return INITIAL[(league-1)%10]
def final_status(league):return FINAL[(league-1)%10]
def expected_phase_rows(n,mode):
    g=n//10
    return dict(pre=2*g,drafting=3*g,post=g,in_season=g,completed=2*g) if mode=='dirty' else dict(pre=0,drafting=g,post=0,in_season=0,completed=g)
def expected_touched(n,mode):return [i for i in range(1,n+1) if (i-1)%10 in ([0,1,2,3,4,5,6,9] if mode=='dirty' else [6])]
def expected_status_changes(n,mode):return [i for i in range(1,n+1) if initial_status(i)!=final_status(i)] if mode=='dirty' else []


def expected_read(call):
    if call in ['denied','missing']:return None
    if call=='detail':return dict(id=1,name='League 1',sport=1,status='Pre-Draft',seasonYear=2026,numPlayers=8,currentWeekId=13,currentWeekNumber=13)
    return [dict(leagueId=1,leagueName='League 1',status='Pre-Draft',memberId=2,teamName='Team 2',seasonPoints=Decimal(336),currentWeekId=13,currentWeekNumber=13,numPlayers=8,seasonYear=2026)]


def projection(call,result):
    expected=expected_read(call)
    if expected is None:
        if result is not None:raise AssertionError('Denied/missing league returned data')
        return None
    if call=='mine':
        if len(result)!=1:raise AssertionError('Sparse reader scope changed')
        return [{k:r[k] for k in expected[0]} for r in result]
    return {k:result[k] for k in expected}


def read_signature(value):return base.signature([] if value is None else value if isinstance(value,list) else [value])


def classify(statement):
    sql=' '.join(statement.split())
    if sql.startswith('UPDATE "League" l'):
        for status,role in PHASES.items():
            if f"SET status = '{status}'" in sql:return role
    if sql.startswith('SELECT l.*,') or ('FROM "LeagueMember" lm' in sql and 'SUM(wts."pointsAwarded")' in sql):return 'read'
    if sql.startswith('SELECT l.id FROM "League" l'):
        return 'candidates' if 'ORDER BY l.id' in sql else 'authorize'
    if sql.startswith('SELECT "leagueId" FROM "DraftState"'):return 'state_lock' if 'FOR UPDATE' in sql else 'state_check'
    if sql.startswith('SELECT id FROM "League"'):return 'league_lock'
    raise AssertionError('Unclassified lifecycle/read statement')


def validate_current(call, sequence, touched, changed, mode):
    wanted = ['candidates']
    if call not in ('denied','missing'):
        wanted += ['state_lock','league_lock','state_check','authorize',*PHASES.values(),'read']
    if sequence != wanted:raise AssertionError('Current lifecycle statement sequence changed')
    expected = [1] if mode=='dirty' and call not in ('denied','missing') else []
    if touched!=expected or changed!=expected:raise AssertionError('Current scoped touched/status IDs changed')


class Tracker:
    def __init__(self):self.enabled=False;self.reset()
    def reset(self):self.counts=Counter();self.phase_rows=Counter();self.examples={};self.sequence=[]
    def before(self,conn,cursor,statement,parameters,context,executemany):
        if self.enabled:
            role=classify(statement);context._mod020_role=role;self.counts[role]+=1;self.sequence.append(role);self.examples.setdefault(role,dict(sql=statement,parameters=parameters))
    def after(self,conn,cursor,statement,parameters,context,executemany):
        if self.enabled and context._mod020_role in PHASES.values():self.phase_rows[context._mod020_role]+=cursor.rowcount


def seed(conn,n):
    facts=base.seed(conn,n);facts['pre_override_seed_status_counts']=dict(active=facts.pop('active_leagues'),completed=facts.pop('completed_leagues'))
    conn.execute(text('''INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES
      (2025,1,2025,current_date-90,current_date-30),(2026,1,2026,current_date-30,current_date+30),(2027,1,2027,current_date+30,current_date+90)'''))
    conn.execute(text('''UPDATE "League" SET "seasonYear"=CASE (id-1)%10 WHEN 3 THEN 2027 WHEN 5 THEN 2025 WHEN 6 THEN 2025 WHEN 9 THEN 1800 ELSE 2026 END'''))
    conn.execute(text('''INSERT INTO "DraftState" ("leagueId",status) SELECT id,CASE (id-1)%10 WHEN 1 THEN 'live' WHEN 2 THEN 'paused' WHEN 6 THEN 'live' ELSE 'complete' END FROM "League" WHERE (id-1)%10 IN (1,2,3,4,5,6,8)'''))
    observed_day=conn.exec_driver_sql("SELECT (now() AT TIME ZONE 'UTC')::date").scalar_one();conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()
    facts.update(observed_utc_day=str(observed_day),groups=10,group_size=n//10,initial_status_counts=dict(Counter(initial_status(i) for i in range(1,n+1))),final_status_counts=dict(Counter(final_status(i) for i in range(1,n+1))),all_timezones='UTC')
    return facts


def prepare(engine,mode):
    with engine.begin() as conn:
        conn.execute(text('''UPDATE "League" SET status=CASE (id-1)%10 WHEN 0 THEN 'In-Season' WHEN 1 THEN 'Pre-Draft' WHEN 2 THEN 'Pre-Draft' WHEN 3 THEN 'Pre-Draft' WHEN 4 THEN 'Pre-Draft' WHEN 5 THEN 'In-Season' WHEN 6 THEN 'Completed' WHEN 7 THEN 'Completed' WHEN 8 THEN 'In-Season' ELSE 'Post-Draft' END,"updatedAt"=:epoch'''),dict(epoch=EPOCH))
    if mode=='steady':
        LeagueLifecycleService(engine).synchronize_for_job()
        with engine.begin() as conn:conn.execute(text('UPDATE "League" SET "updatedAt"=:epoch'),dict(epoch=EPOCH))


def snapshot(engine):
    with engine.connect() as conn:return [dict(r) for r in conn.execute(text('SELECT id,status,"updatedAt" FROM "League" ORDER BY id')).mappings()]


def measure(engine,n,call,mode):
    tracker=Tracker();event.listen(engine,'before_cursor_execute',tracker.before);event.listen(engine,'after_cursor_execute',tracker.after)
    query=LeagueLifecycleQueryService(engine);samples=[];examples={};signature=None;status_signature=None
    try:
        for iteration in range(6):
            prepare(engine,mode);before=snapshot(engine)
            tracker.reset();tracker.enabled=True;start=time.perf_counter()
            try:
                actor=UserActor(99999999 if call=='denied' else 2,'synthetic')
                result=query.mine(actor,'all') if call=='mine' else query.details(actor,n+100 if call=='missing' else 1)
            finally:elapsed=(time.perf_counter()-start)*1000;tracker.enabled=False
            projected=projection(call,result);signature=read_signature(projected);base.assert_equivalent(read_signature(expected_read(call)),signature)
            after=snapshot(engine)
            touched=[r['id'] for r in after if r['updatedAt']!=EPOCH];changed=[a['id'] for b,a in zip(before,after) if b['status']!=a['status']]
            validate_current(call,tracker.sequence,touched,changed,mode)
            expected_states=[dict(id=i,status=final_status(i) if mode=='steady' or (i==1 and call not in ('denied','missing')) else initial_status(i)) for i in range(1,n+1)]
            status_signature=base.signature([dict(id=r['id'],status=r['status']) for r in after]);base.assert_equivalent(base.signature(expected_states),status_signature)
            expected_phases={role:1 if role=='pre' and mode=='dirty' else 0 for role in PHASES.values()} if call not in ('denied','missing') else {}
            if dict(tracker.phase_rows)!=expected_phases:raise AssertionError('Scoped phase counts changed')
            examples.update(tracker.examples)
            if iteration:samples.append(dict(total_ms=elapsed,sequence=list(tracker.sequence),statements=dict(tracker.counts),phase_rows=dict(tracker.phase_rows),row_updates=sum(tracker.phase_rows.values()),touched_ids=touched,changed_ids=changed))
        return dict(contract='authorized-scoped-v2',call=call,mode=mode,leagues=n,result_projection=signature,final_statuses=status_signature,samples=samples,median_total_ms=base.statistics.median(s['total_ms'] for s in samples),statement_examples=examples,invocations=6)
    finally:
        tracker.enabled=False;event.remove(engine,'before_cursor_execute',tracker.before);event.remove(engine,'after_cursor_execute',tracker.after)


def run_tier(admin,n,report):
    record=None
    try:
        with base.owned_database(admin) as database:
            record=dict(name=database,cleanup='pending');report['databases'].append(record)
            engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=database,**base.LOCAL))
            try:
                with engine.connect() as conn:
                    base.schema(conn);facts=seed(conn,n);settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','TimeZone','shared_buffers','work_mem','statement_timeout','lock_timeout']}
                measurements=[measure(engine,n,call,mode) for call in CALLS for mode in ['dirty','steady']]
                return dict(leagues=n,fixture=facts,settings=settings,measurements=measurements)
            finally:engine.dispose()
    finally:
        if record is not None:verify_cleanup(admin,record)


def run(directory,manifest,tiers,connect=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);run_id=uuid4().hex;artifact=directory/f'mod-020-lifecycle-{run_id}.json'
    inputs=[base.BASELINE,*base.MIGRATIONS,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod020_lifecycle.py','api/endpoints/league/lifecycle/service.py','api/endpoints/league/lifecycle/query_service.py','api/endpoints/league/lifecycle/repository.py','api/endpoints/league/reads/service.py','api/endpoints/league/reads/repository.py','api/endpoints/league/leagueEndpoints.py','api/utils/authorization.py','api/utils/conference_membership.py']
    report=dict(date='2026-11-16',run_id=run_id,started_at=datetime.now(timezone.utc).isoformat(),result='RUNNING',scope='Synthetic authorized scoped lifecycle/read contract v2; no production latency claim',tiers=[],databases=[],cleanup='no database created',provenance={},limits=['Synthetic ten equal status groups/allUTC/relative dates;no production mix/timezoneboundary claim','Explicit scoped coordinator with atomic transaction, no HTTP/JWT/concurrency proof in this measurement','Selected readbusinessprojection only, timestamp identity checked separately; resets/convergence outside timing'])
    def persist():
        save_json(artifact,report);save_json(Path(manifest),dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        report['provenance']={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in inputs}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        for n in tiers:
            print(f'MOD020 lifecycle leagues {n}: starting',flush=True);report['tiers'].append(run_tier(admin,n,report));persist();print(f'MOD020 lifecycle leagues {n}: PASS',flush=True)
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
    directory=base.ROOT/'docs/modernization/evidence';run(directory,directory/'mod-020-lifecycle-current-2026-11-16.json',args.tier or SIZES)
if __name__=='__main__':main()
