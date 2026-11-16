"""Audit-only search retrieval and tie-order probes on owned marked localhost."""
import argparse
from datetime import datetime,timezone
import hashlib,time
from pathlib import Path
from uuid import uuid4
import psycopg2
from sqlalchemy import create_engine,text,event
import measure_mod017 as base
from measure_mod017_transactions import Capture,save_json,verify_cleanup
from endpoints.league.reads.repository import LeagueReadRepository
from endpoints.league.reads.service import LeagueReadService

SIZES=(1000,10000,100000)
ORDER='ORDER BY similarity(l.name, :q) DESC, l.name ASC'


def eligible_ids(n,sport):return [i for i in range(1,n+1) if (i-1)%10<7 and (sport is None or (2 if i%7==0 else 1)==sport)]
def expected_row(i):return dict(id=i,name='Audit League',sport=2 if i%7==0 else 1,numPlayers=8,status='Pre-Draft',draftDate=None,isDiscoverable=True,commissioner=1,commissionerDisplayName='Audit commissioner')
def expected_ids(n,case):return [] if case['params']['q']=='Absent' else eligible_ids(n,case['sport'])[case['params']['offset']:case['params']['offset']+case['params']['limit']]
def probe_sql(sql):
    if sql.count(ORDER)!=1:raise AssertionError('Expected production ORDER BY shape changed')
    return sql.replace(ORDER,ORDER+', l.id ASC',1)


def capture_queries(n):
    repo=LeagueReadRepository();total=len(eligible_ids(n,None));cases=[]
    for name,sport,offset,q in [('all_first',None,0,'Audit League'),('all_middle',None,min(total//2,10000),'Audit League'),('all_max_offset',None,10000,'Audit League'),('sport_one',1,0,'Audit League'),('sport_two',2,0,'Audit League'),('miss',None,0,'Absent')]:
        c=Capture();repo.search_discoverable(c,q,sport,50,offset)
        case=dict(name=name,sport=sport,sql=c.statement,params=c.params);case['expected_rows']=len(expected_ids(n,case));cases.append(case)
    return cases


def validate_rows(n,case,rows,reference=False):
    ids=[r['id'] for r in rows]
    if len(ids)!=case['expected_rows'] or len(set(ids))!=len(ids):raise AssertionError('Wrong page count/duplicate within page')
    for r in rows:
        i=r['id']
        if not 1<=i<=n or (i-1)%10>=7 or case['params']['q']=='Absent' or case['sport'] is not None and r['sport']!=case['sport']:raise AssertionError('Search scope/visibility changed')
        base.assert_equivalent(base.signature([expected_row(i)]),base.signature([r]))
    if reference and ids!=expected_ids(n,case):raise AssertionError('ID tie probe order changed')


def seed(conn,n):
    for sql in [
      '''INSERT INTO "Sport" (id,name) VALUES (1,'Basketball'),(2,'Football')''',
      '''INSERT INTO "User" (id,email,"displayName") VALUES (1,'audit@example.test','Audit commissioner')''',
    ]:conn.exec_driver_sql(sql)
    conn.execute(text('''INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear","isDiscoverable") SELECT i,CASE (i-1)%10 WHEN 7 THEN 'Different League' WHEN 8 THEN 'Other League' ELSE 'Audit League' END,CASE WHEN i%7=0 THEN 2 ELSE 1 END,8,'Pre-Draft','{}',1,2026,(i-1)%10<>9 FROM generate_series(1,:n) i'''),dict(n=n))
    conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()
    actual=conn.exec_driver_sql('SELECT count(*) FROM "League"').scalar_one()
    if actual!=n:raise AssertionError('Search fixture count mismatch')
    return dict(leagues=n,public_equal_name_matches=len(eligible_ids(n,None)),sport1_matches=len(eligible_ids(n,1)),sport2_matches=len(eligible_ids(n,2)),private_leagues=n//10,unmatched_public_leagues=n//5,all_matches_same_name=True)


def measure_sql(conn,n,case,reference):
    sql=probe_sql(case['sql']) if reference else case['sql'];params=case['params'];conn.execute(text(sql),params).fetchall()
    plan=conn.execute(text('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+sql),params).scalar_one()[0];samples=[]
    for _ in range(5):
        start=time.perf_counter();raw=conn.execute(text(sql),params).mappings().all();elapsed=(time.perf_counter()-start)*1000;rows=[dict(r) for r in raw];validate_rows(n,case,rows,reference)
        samples.append(dict(client_ms=elapsed,result=base.signature(rows),ids=[r['id'] for r in rows]))
    return dict(name=case['name'],variant='id_probe' if reference else 'current',sql=sql,params=params,expected_rows=case['expected_rows'],samples=samples,median_client_ms=base.statistics.median(s['client_ms'] for s in samples),distinct_ordered_fingerprints=len({s['result']['sha256'] for s in samples}),plan=plan)


def measure_service(engine,n,cases):
    service=LeagueReadService(engine);query_count=0;enabled=False;records=[]
    def before(*args):
        nonlocal query_count
        if enabled:query_count+=1
    event.listen(engine,'before_cursor_execute',before)
    try:
        for case in [*cases,dict(name='short',params=dict(q=' a ',limit=50,offset=0),sport=None,expected_rows=0)]:
            samples=[]
            for iteration in range(6):
                query_count=0;enabled=True;p=case['params'];start=time.perf_counter()
                try:rows=service.search_public(p['q'],case['sport'],p['limit'],p['offset'])
                finally:elapsed=(time.perf_counter()-start)*1000;enabled=False
                if query_count!=(0 if case['name']=='short' else 1):raise AssertionError('Search service query count changed')
                if case['name']=='short':
                    if rows:raise AssertionError('Short query returned rows')
                else:validate_rows(n,case,rows)
                if iteration:samples.append(dict(service_ms=elapsed,queries=query_count,result=base.signature(rows),ids=[r['id'] for r in rows]))
            records.append(dict(name=case['name'],samples=samples,median_service_ms=base.statistics.median(s['service_ms'] for s in samples)))
        return records
    finally:event.remove(engine,'before_cursor_execute',before)


def page_walk(conn,n,reference):
    case=capture_queries(n)[0];all_ids=[];pages=[];wanted=eligible_ids(n,None)
    for offset in range(0,len(wanted),50):
        c=dict(case,params=dict(case['params'],offset=offset));c['expected_rows']=min(50,len(wanted)-offset);sql=probe_sql(c['sql']) if reference else c['sql'];rows=[dict(r) for r in conn.execute(text(sql),c['params']).mappings()];validate_rows(n,c,rows,reference);ids=[r['id'] for r in rows];all_ids.extend(ids);pages.append(dict(offset=offset,ids=ids))
    duplicates=len(all_ids)-len(set(all_ids));missing=sorted(set(wanted)-set(all_ids))
    if reference and (duplicates or missing or all_ids!=wanted):raise AssertionError('ID tie probe failed full small-fixture traversal')
    return dict(variant='id_probe' if reference else 'current',pages=pages,expected_total=len(wanted),returned_rows=len(all_ids),unique_ids=len(set(all_ids)),duplicate_occurrences=duplicates,missing_ids=missing,complete_without_duplicates=not duplicates and not missing)


def structural_catalog(rows):return sorted([(r['table_name'],r['name'],r['definition'],r['unique']) for r in rows])


def run_tier(admin,n,report):
    record=None
    try:
        with base.owned_database(admin) as database:
            record=dict(name=database,cleanup='pending');report['databases'].append(record)
            engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=database,**base.LOCAL))
            try:
                with engine.connect() as conn:
                    base.schema(conn);facts=seed(conn,n);cases=capture_queries(n);before_catalog=base.catalog(conn);settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','shared_buffers','work_mem','jit','statement_timeout','lock_timeout']};layouts={}
                    for layout in ['original','descending_heap']:
                        if layout=='descending_heap':
                            conn.exec_driver_sql('CREATE INDEX mod018_heap_order ON "League" (id DESC)');conn.exec_driver_sql('CLUSTER "League" USING mod018_heap_order');conn.exec_driver_sql('DROP INDEX mod018_heap_order');conn.exec_driver_sql('ANALYZE');conn.commit()
                        sql_records=[measure_sql(conn,n,c,reference) for reference in [False,True] for c in cases];conn.commit();services=measure_service(engine,n,cases)
                        walks=[page_walk(conn,n,r) for r in [False,True]] if n==1000 else [];conn.commit();layouts[layout]=dict(sql_measurements=sql_records,service_measurements=services,page_walks=walks)
                    after_catalog=base.catalog(conn)
                    if structural_catalog(before_catalog)!=structural_catalog(after_catalog):raise AssertionError('Schema index definitions changed after private layout probe')
                    changes={variant:next(x for x in layouts['original']['sql_measurements'] if x['variant']==variant and x['name']=='all_first')['samples'][0]['ids']!=next(x for x in layouts['descending_heap']['sql_measurements'] if x['variant']==variant and x['name']=='all_first')['samples'][0]['ids'] for variant in ['current','id_probe']}
                    if changes['id_probe']:raise AssertionError('Reference ordering changed across layouts')
                    return dict(leagues=n,fixture=facts,settings=settings,before_index_catalog=before_catalog,after_index_catalog=after_catalog,first_page_changed=changes,layouts=layouts)
            finally:engine.dispose()
    finally:
        if record is not None:verify_cleanup(admin,record)


def run(directory,manifest,tiers,connect=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);run_id=uuid4().hex;artifact=directory/f'mod-018-search-{run_id}.json'
    inputs=[base.BASELINE,*base.MIGRATIONS,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod018_search.py','api/endpoints/league/reads/service.py','api/endpoints/league/reads/repository.py','api/endpoints/league/leagueEndpoints.py','api/utils/authorization.py','api/utils/conference_membership.py']
    report=dict(date='2026-11-16',run_id=run_id,started_at=datetime.now(timezone.utc).isoformat(),result='RUNNING',scope='Synthetic discoverable search retrieval/tie-order measurements only; optimization deferred',tiers=[],databases=[],cleanup='no database created',provenance={},limits=['All matching names identical,sport/private fixture distributions synthetic;no other relevance-ranking proof','ID tie probe/heapCLUSTER exist only in owned fixture,not app optimization','Small1000fixture fullwalk only;large offsets sampled withinHTTPcap10000,no large fulltraversal/production/cache/concurrency claim'])
    def persist():
        save_json(artifact,report);save_json(Path(manifest),dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        report['provenance']={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in inputs}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        for n in tiers:
            print(f'MOD018 search leagues {n}: starting',flush=True);report['tiers'].append(run_tier(admin,n,report));persist();print(f'MOD018 search leagues {n}: PASS',flush=True)
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
    directory=base.ROOT/'docs/modernization/evidence';run(directory,directory/'mod-018-search-current-2026-11-16.json',args.tier or SIZES)
if __name__=='__main__':main()
