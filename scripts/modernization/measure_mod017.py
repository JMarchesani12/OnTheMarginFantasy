"""MOD017 synthetic PostgreSQL plans. Fixed marked loopback only; no DSN/app/jobs.

Run against a task-owned ephemeral server on55439. Each tier owns a new UUID DB;
only this runner's created DB is dropped, including on Python exceptions.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys
import time
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'api'))
from endpoints.league.reads.repository import LeagueReadRepository
from utils.ownership_reads import team_ownership_rows

MARKER='otm-modernization-assessment-20261029-synthetic-only'
LOCAL=dict(host='127.0.0.1',port=55439,user='postgres',password='synthetic-local-only',
           sslmode='disable',connect_timeout=3,options='-c statement_timeout=120000 -c lock_timeout=5000')
SIZES=(100,1000,5000)
MIGRATIONS=['api/migrations/20261104_user_identity_unique.sql','api/migrations/20261104_week_score_identity.sql','api/migrations/20261104_ownership_integrity.sql']
BASELINE='db/baselines/20261029/001_schema.sql'
CANDIDATES={
 'member_reverse':('CREATE INDEX mod017_member_reverse ON "LeagueMember" ("userId","leagueId")','own'),
 'ownership_team':('CREATE INDEX mod017_ownership_team ON "LeagueTeamSlot" ("leagueId","sportTeamId") INCLUDE ("memberId","acquiredWeek","droppedWeek")','ownership'),
 'ownership_member_team':('CREATE INDEX mod017_ownership_member_team ON "LeagueTeamSlot" ("leagueId","memberId","sportTeamId") INCLUDE ("acquiredWeek","droppedWeek")','ownership'),
}


def guard_target(host,port,marker):
    if host!='127.0.0.1' or port!=55439 or marker!=MARKER:
        raise RuntimeError('Refusing nonlocal or unmarked synthetic server')


def new_database_name():return 'otm_mod017_'+uuid4().hex


def cleanup_owned_database(admin,name,created):
    if not re.fullmatch(r'otm_mod017_[0-9a-f]{32}',name):raise RuntimeError('Refusing unowned database name')
    if created:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


@contextmanager
def owned_database(admin):
    name=new_database_name()
    created=False
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            guard_target(LOCAL['host'],LOCAL['port'],cursor.fetchone()[0])
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created=True
        yield name
    finally:cleanup_owned_database(admin,name,created)


class Capture:
    def execute(self,statement,params):
        self.statement=str(statement);self.params=dict(params)
        return []


def capture_queries(n):
    cases=[]
    def add(name,family,callback):
        conn=Capture();callback(conn)
        cases.append(dict(name=name,family=family,sql=conn.statement,params=conn.params))
    repo=LeagueReadRepository()
    for name,user,stage in [('hot_all',1,'all'),('sparse_all',2,'all'),('hot_active',1,'active'),('hot_completed',1,'completed'),('absent_all',7*n+10000,'all')]:
        add('own_'+name,'own',lambda c,u=user,s=stage:repo.own_leagues(c,u,s))
    league=n//2+1;member=(league-1)*8+1
    for name,team,week,owner in [('any_current',1,13,'any'),('member_current',1,13,member),('member_history',1,4,member),('absent_team',99999,13,'any'),('wrong_member',1,13,member+1),('null_member',1,13,None),('before_acquisition',1,0,'any'),('last_member',32,13,member+7)]:
        def callback(c,t=team,w=week,m=owner):
            if m=='any':return team_ownership_rows(c,league,t,w)
            return team_ownership_rows(c,league,t,w,m)
        add('ownership_'+name,'ownership',callback)
    return cases


def expected_counts(n):return {'League':n,'LeagueMember':8*n,'Week':13*n,'WeeklyTeamScore':96*n,'LeagueTeamSlot':160*n}


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()


def signature(rows):
    data=canonical(rows)
    return dict(rows=len(rows),canonical_json_bytes=len(data),sha256=hashlib.sha256(data).hexdigest())


def assert_equivalent(expected,actual):
    if expected!=actual:raise AssertionError('Query output/cardinality/bytes changed during experiment')


def schema(conn):
    conn.exec_driver_sql('CREATE SCHEMA auth; CREATE TABLE auth.users (id uuid PRIMARY KEY); CREATE EXTENSION pg_trgm;')
    conn.exec_driver_sql((ROOT/BASELINE).read_text())
    conn.commit()
    # Migrations are exact checked-in scripts, run before deterministic clean rows exist.
    for path in MIGRATIONS:
        conn.exec_driver_sql((ROOT/path).read_text());conn.commit()
    # Migration SET LOCAL budgets end at COMMIT; restore fixed session budgets.
    conn.exec_driver_sql("SET statement_timeout='120s'; SET lock_timeout='5s';")
    conn.commit()


def seed(conn,n):
    if n not in SIZES:raise ValueError('Unknown fixed fixture tier')
    anchor=conn.execute(text('SELECT now()')).scalar_one()
    statements=[
      'INSERT INTO "Sport" (id,name,"maxPlayersToHaveMaxRounds","maxDraftRounds") VALUES (1,\'Synthetic\',8,4)',
      f'''INSERT INTO "User" (id,email,"displayName") SELECT i,'synthetic-'||i||'@example.test','User '||i FROM generate_series(1,{7*n+1}) i''',
      f'''INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear") SELECT i,'League '||i,1,8,CASE WHEN i%3=0 THEN 'Completed' ELSE 'In-Season' END,jsonb_build_object('draft',jsonb_build_object('numberOfRounds',4),'timezone','UTC'),1,2026 FROM generate_series(1,{n}) i''',
      f'''INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") SELECT (l-1)*8+m,l,CASE WHEN m=1 THEN 1 ELSE (l-1)*7+m END,'Team '||m,m FROM generate_series(1,{n}) l CROSS JOIN generate_series(1,8) m''',
      '''INSERT INTO "School" (id,name) SELECT i,'School '||i FROM generate_series(1,32) i''',
      '''INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName") SELECT i,i,1,'Sport team '||i FROM generate_series(1,32) i''',
      f'''INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate") SELECT (l-1)*13+w,l,w,:anchor + (w-13)*interval '7 days'-interval '1 day',:anchor+(w-13)*interval '7 days'+interval '6 days' FROM generate_series(1,{n}) l CROSS JOIN generate_series(1,13) w''',
      f'''INSERT INTO "WeeklyTeamScore" ("leagueId","weekId","memberId",rank,"pointsAwarded","pointDifferential") SELECT l,(l-1)*13+w,(l-1)*8+m,m,4*(9-m),4*(9-m) FROM generate_series(1,{n}) l CROSS JOIN generate_series(1,8) m CROSS JOIN generate_series(1,12) w''',
      f'''INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","droppedWeek","acquiredVia") SELECT l,(l-1)*8+m,(m-1)*4+t,1+(h-1)*3,CASE WHEN h=5 THEN NULL ELSE 1+h*3 END,'DRAFT' FROM generate_series(1,{n}) l CROSS JOIN generate_series(1,8) m CROSS JOIN generate_series(1,4) t CROSS JOIN generate_series(1,5) h''',
    ]
    for statement in statements:conn.execute(text(statement),{'anchor':anchor})
    conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()
    counts={table:conn.exec_driver_sql(f'SELECT count(*) FROM "{table}"').scalar_one() for table in expected_counts(n)}
    if counts!=expected_counts(n):raise AssertionError('Fixture cardinality differs from declared tier')
    return dict(anchor=anchor.isoformat(),counts=counts,user_count=7*n+1,hot_user_memberships=n,sparse_user_memberships=1,current_week=13,scored_weeks=12,teams_contributing_to_score_value=4,active_leagues=n-n//3,completed_leagues=n//3)


def catalog(conn):
    rows=conn.exec_driver_sql('''SELECT t.relname AS table_name,i.relname AS name,am.amname AS method,
      x.indisunique AS unique,x.indisprimary AS primary,x.indisexclusion AS exclusion,
      x.indisvalid AS valid,x.indisready AS ready,x.indnullsnotdistinct AS nulls_not_distinct,
      x.indnkeyatts AS key_count,x.indnatts AS total_columns,x.indkey::text AS keys,
      x.indclass::text AS operator_classes,x.indcollation::text AS collations,x.indoption::text AS options,
      pg_get_expr(x.indpred,x.indrelid) AS predicate,pg_get_expr(x.indexprs,x.indrelid) AS expressions,
      pg_get_indexdef(i.oid) AS definition,pg_relation_size(i.oid) AS bytes,
      ARRAY(SELECT c.conname FROM pg_constraint c WHERE c.conindid=i.oid ORDER BY c.conname) AS constraints
      FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_class t ON t.oid=x.indrelid
      JOIN pg_namespace ns ON ns.oid=t.relnamespace JOIN pg_am am ON am.oid=i.relam
      WHERE ns.nspname='public' ORDER BY t.relname,i.relname''').mappings().all()
    return [dict(r) for r in rows]


def structural_groups(indexes):
    fields=['table_name','method','key_count','total_columns','keys','operator_classes','collations','options','predicate','expressions','nulls_not_distinct']
    groups={}
    for index in indexes:groups.setdefault(canonical([index[f] for f in fields]),[]).append(index)
    return [[{'name':i['name'],'unique':i['unique'],'constraints':i['constraints']} for i in group] for group in groups.values() if len(group)>1]


def measure(conn,case):
    statement=text(case['sql']);params=case['params']
    conn.execute(statement,params).fetchall() # warm-up; no cold-cache claim
    plan=conn.execute(text('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+case['sql']),params).scalar_one()[0]
    samples=[];first=None
    for _ in range(5):
        start=time.perf_counter();rows=conn.execute(statement,params).mappings().all();elapsed=(time.perf_counter()-start)*1000
        current=signature([dict(row) for row in rows])
        if first is not None:assert_equivalent(first,current)
        first=current;samples.append(elapsed)
    return dict(**case,result=first,client_execute_fetch_ms=dict(samples=samples,median=statistics.median(samples),min=min(samples),max=max(samples)),plan=plan)


def run_tier(admin,n):
    with owned_database(admin) as name:
        # Explicit fields, no DSN/environment application credentials.
        engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**LOCAL))
        try:
            with engine.connect() as conn:
                schema(conn);facts=seed(conn,n)
                settings={key:conn.exec_driver_sql('SHOW '+key).scalar_one() for key in ['server_version','shared_buffers','work_mem','effective_cache_size','random_page_cost','seq_page_cost','jit','max_parallel_workers_per_gather','statement_timeout','lock_timeout']}
                baseline_indexes=catalog(conn);cases=capture_queries(n);results={};signatures={}
                results['baseline']=[measure(conn,c) for c in cases]
                for result in results['baseline']:signatures[result['name']]=result['result']
                experiments={}
                for candidate,(ddl,family) in CANDIDATES.items():
                    start=time.perf_counter();conn.exec_driver_sql(ddl);build_ms=(time.perf_counter()-start)*1000
                    conn.exec_driver_sql('ANALYZE');conn.commit()
                    results[candidate]=[measure(conn,c) for c in cases if c['family']==family]
                    for result in results[candidate]:assert_equivalent(signatures[result['name']],result['result'])
                    index=catalog(conn);record=next(i for i in index if i['name']=='mod017_'+candidate)
                    experiments[candidate]=dict(ddl=ddl,build_ms=build_ms,index=record)
                    conn.exec_driver_sql('DROP INDEX "mod017_'+candidate+'"');conn.commit()
                sizes={table:conn.exec_driver_sql(f'SELECT pg_total_relation_size(\'"{table}"\')').scalar_one() for table in expected_counts(n)}
                return dict(tier=n,fixture=facts,settings=settings,baseline_indexes=baseline_indexes,same_structural_keys=structural_groups(baseline_indexes),experiments=experiments,relation_bytes=sizes,measurements=results)
        finally:engine.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tier',type=int,choices=SIZES,action='append')
    args=parser.parse_args()
    tiers=args.tier or SIZES
    output=ROOT/'docs/modernization/evidence/mod-017-query-baselines-2026-11-11.json'
    report=dict(date='2026-11-11',started_at=datetime.now(timezone.utc).isoformat(),scope='Two-family synthetic PostgreSQL baselines; not production traffic or endpoint latency',provenance={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [BASELINE,*MIGRATIONS,'api/endpoints/league/reads/repository.py','api/utils/ownership_reads.py']},schema_limits=['001_schema plus MOD006/008/010 only; access/RLS002 and later unrelated seasonal/calendar migrations not applied','synthetic auth.users prerequisite, no Supabase role/platform equivalence','WeeklyTeamScore is one member/week aggregate; design row count corrected to96 per league','all samples warm, no production workload/cold-cache/ongoing write-cost claim'],tiers=[],result='RUNNING')
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    try:
        for n in tiers:
            print(f'MOD017 tier {n}: seeding/measuring',flush=True)
            report['tiers'].append(run_tier(admin,n));output.write_text(json.dumps(report,indent=2,default=str)+'\n')
            print(f'MOD017 tier {n}: PASS; owned database removed',flush=True)
        with admin.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_database WHERE datname LIKE 'otm_mod017_%'")
            # Record, never clean an unrelated run's database.
            report['remaining_mod017_database_count']=cursor.fetchone()[0]
        report['result']='PASS';report['finished_at']=datetime.now(timezone.utc).isoformat()
        output.write_text(json.dumps(report,indent=2,default=str)+'\n')
        print(str(output),flush=True)
    finally:admin.close()

if __name__=='__main__':main()
