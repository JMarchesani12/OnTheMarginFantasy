"""Synthetic transaction-read plans; fixed marked localhost only, no DSNs/app/jobs.

Prior MOD017 utilities/evidence remain unchanged. Each run has a unique artifact;
the current-run manifest changes before connecting and records failure explicitly.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from uuid import uuid4

import psycopg2
from sqlalchemy import create_engine, text
import measure_mod017 as base
from endpoints.transaction.repository import TransactionRepository
from endpoints.transaction.workflow_repository import TransactionWorkflowRepository
from endpoints.scoring.weekly_repository import WeeklyCompletionRepository

CANDIDATES={
 'tx_status_time':'CREATE INDEX mod017_tx_status_time ON "Transaction" ("leagueId",status,"createdAt" DESC,id DESC)',
 'tx_time_cover':'CREATE INDEX mod017_tx_time_cover ON "Transaction" ("leagueId","createdAt" DESC,id DESC) INCLUDE (status)',
 'tx_pending_partial':"CREATE INDEX mod017_tx_pending_partial ON \"Transaction\" (\"leagueId\",id) WHERE status='PENDING_APPLY'",
}

class EmptyRows:
    def mappings(self):return self
    def all(self):return []
    def fetchall(self):return []
    def __iter__(self):return iter([])

class Capture(base.Capture):
    def execute(self,statement,params):
        super().execute(statement,params)
        return EmptyRows()


def capture_queries(n,anchor):
    league=(n//20)*10 # always a tenth league with one pending transaction
    member=(league-1)*8+1
    repo=TransactionRepository();workflow=TransactionWorkflowRepository();weekly=WeeklyCompletionRepository()
    cases=[]
    def add(name,family,expected,fn):
        conn=Capture();fn(conn)
        cases.append(dict(name=name,family=family,expected_rows=expected,sql=conn.statement,params=conn.params))
    for name,status,user,lid,expected in [('all',None,1,league,100),('pending','PENDING_APPLY',1,league,1),('proposed','PROPOSED',1,league,19),('missing_status','UNKNOWN',1,league,0),('denied',None,-1,league,0),('missing_league',None,1,n+100,0)]:
        add('list_'+name,'list',expected,lambda c,s=status,u=user,l=lid:repo.list_transactions(c,l,s,u))
    for name,mid,uid,lid,expected in [('participant',member,1,league,10),('other_member',member+2,(league-1)*7+3,league,10),('denied',member,-1,league,0),('missing_league',member,1,n+100,0)]:
        params=dict(league_id=lid,member_id=mid,reader_user_id=uid)
        add('open_'+name,'open',expected,lambda c,p=params:workflow.open_trades(c,p))
    add('weekly_candidates','weekly',n//10,lambda c:weekly.candidates(c,datetime.fromisoformat(anchor)))
    return cases


def validate_result(case,result):
    if result['result']['rows']!=case['expected_rows']:raise AssertionError('Unexpected query result cardinality: '+case['name'])
    if len(result['client_execute_fetch_ms']['samples'])!=5:raise AssertionError('Incorrect timing sample count')


def seed_transactions(conn,n,anchor):
    # No historical week backlog: isolate actual candidate query's pending branch.
    conn.exec_driver_sql('UPDATE "Week" SET "scoringComplete"=true')
    conn.execute(text(f'''INSERT INTO "Transaction" (id,"leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds","createdAt")
      SELECT (l-1)*100+i,l,(l-1)*13+13,CASE WHEN i%2=0 THEN 'TRADE' ELSE 'FREE_AGENT' END,
      (l-1)*8+1,(l-1)*8+CASE WHEN i%2=0 THEN 2 ELSE 1 END,
      CASE WHEN i=100 AND l%10=0 THEN 'PENDING_APPLY' WHEN i<100 AND i%5=0 THEN 'PROPOSED' WHEN i%3=0 THEN 'CANCELLED' ELSE 'COMPLETED' END,
      jsonb_build_array(1),jsonb_build_array(5),CAST(:anchor AS timestamptz)-(101-i)*interval '1 minute'
      FROM generate_series(1,{n}) l CROSS JOIN generate_series(1,100) i'''),{'anchor':anchor})
    conn.execute(text(f'''INSERT INTO "TransactionVote" ("transactionId","leagueMemberId",veto)
      SELECT (l-1)*100+i,(l-1)*8+3,(i%20=0)
      FROM generate_series(1,{n}) l CROSS JOIN generate_series(10,100,10) i'''))
    conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()
    observed={table:conn.exec_driver_sql(f'SELECT count(*) FROM "{table}"').scalar_one() for table in ['Transaction','TransactionVote']}
    pending=conn.exec_driver_sql('SELECT count(*) FROM "Transaction" WHERE status=\'PENDING_APPLY\'').scalar_one()
    if observed!={'Transaction':n*100,'TransactionVote':n*10} or pending!=n//10:raise AssertionError('Transaction fixture cardinality mismatch')
    return dict(**observed,pending=pending,pending_fraction=0.001,events_per_league=100,unique_created_time_per_league=True,team_ids_per_side=1,all_weeks_scoring_complete=True)


def measure(conn,case):
    result=base.measure(conn,case);validate_result(case,result);return result


def verify_cleanup(admin,record):
    try:
        with admin.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM pg_database WHERE datname=%s',(record['name'],))
            record['cleanup']='removed' if cursor.fetchone()[0]==0 else 'still present'
    except Exception:record['cleanup']='verification unavailable'


def run_tier(admin,n,report):
    record=None
    try:
        with base.owned_database(admin) as name:
            record=dict(name=name,cleanup='pending');report['databases'].append(record)
            engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
            try:
                with engine.connect() as conn:
                    base.schema(conn);facts=base.seed(conn,n)
                    facts['transactions']=seed_transactions(conn,n,facts['anchor'])
                    cases=capture_queries(n,facts['anchor']);indexes=base.catalog(conn)
                    settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','shared_buffers','work_mem','effective_cache_size','random_page_cost','seq_page_cost','jit','max_parallel_workers_per_gather','statement_timeout','lock_timeout']}
                    measurements={'baseline':[measure(conn,c) for c in cases]}
                    fingerprints={r['name']:r['result'] for r in measurements['baseline']}
                    experiments={}
                    for name_index,ddl in CANDIDATES.items():
                        start=time.perf_counter();conn.exec_driver_sql(ddl);build_ms=(time.perf_counter()-start)*1000
                        conn.exec_driver_sql('ANALYZE');conn.commit()
                        chosen=[c for c in cases if c['name'] in ['list_pending','weekly_candidates']] if name_index=='tx_pending_partial' else [c for c in cases if c['family']!='weekly']
                        measurements[name_index]=[measure(conn,c) for c in chosen]
                        for result in measurements[name_index]:base.assert_equivalent(fingerprints[result['name']],result['result'])
                        index=next(i for i in base.catalog(conn) if i['name']=='mod017_'+name_index)
                        experiments[name_index]=dict(ddl=ddl,build_ms=build_ms,index=index)
                        conn.exec_driver_sql('DROP INDEX "mod017_'+name_index+'"');conn.commit()
                    relation_bytes={table:conn.exec_driver_sql(f'SELECT pg_total_relation_size(\'"{table}"\')').scalar_one() for table in ['Transaction','TransactionVote','Week']}
                    return dict(tier=n,fixture=facts,settings=settings,baseline_indexes=indexes,experiments=experiments,measurements=measurements,relation_bytes=relation_bytes)
            finally:engine.dispose()
    finally:
        if record is not None:verify_cleanup(admin,record)


def save_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,default=str)+'\n');temporary.replace(path)


def run(directory,manifest,tiers,connect=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    run_id=uuid4().hex;artifact=directory/f'mod-017-transactions-{run_id}.json'
    inputs=[base.BASELINE,*base.MIGRATIONS,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','api/endpoints/transaction/repository.py','api/endpoints/transaction/workflow_repository.py','api/endpoints/scoring/weekly_repository.py']
    report=dict(date='2026-11-13',run_id=run_id,started_at=datetime.now(timezone.utc).isoformat(),result='RUNNING',scope='Synthetic transaction-read baseline; not production or full HTTP latency',tiers=[],databases=[],cleanup='no database created',provenance={},limits=['Low pending density0.1%,single-team arrays,unique timestamps; no dense/tie/large-array claim','Schema/RLS/role/physical-cache/write-cost limits from prior baseline remain','No SQL rewrite/pagination/index rollout; candidate indexes private only'])
    def persist():
        save_json(artifact,report)
        save_json(Path(manifest),dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist() # Before connection, so failures cannot retain a previous current PASS.
    admin=None
    try:
        report['provenance']={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in inputs}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL)
        admin.autocommit=True
        for n in tiers:
            print(f'MOD017 transactions tier {n}: starting',flush=True)
            report['tiers'].append(run_tier(admin,n,report));persist()
            print(f'MOD017 transactions tier {n}: PASS',flush=True)
        if len(report['databases'])!=len(tiers) or any(r['cleanup']!='removed' for r in report['databases']):raise RuntimeError('Owned database cleanup not verified')
        report['cleanup']='verified';report['result']='PASS'
        return report
    except BaseException as error:
        report['result']='FAILED';report['error_type']=type(error).__name__
        if report['databases']:report['cleanup']='verified' if all(r['cleanup']=='removed' for r in report['databases']) else 'incomplete or unverified'
        raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat()
        persist()
        if admin is not None:admin.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tier',type=int,choices=base.SIZES,action='append');args=parser.parse_args()
    directory=base.ROOT/'docs/modernization/evidence'
    run(directory,directory/'mod-017-transactions-current-2026-11-13.json',args.tier or base.SIZES)

if __name__=='__main__':main()
