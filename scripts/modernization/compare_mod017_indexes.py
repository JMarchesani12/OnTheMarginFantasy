"""Controlled current-query index comparisons. Only marked disposable localhost."""
import argparse
from datetime import datetime,timedelta
from pathlib import Path
import statistics
import time
import psycopg2
from sqlalchemy import bindparam,create_engine,text
import measure_mod017 as base
import measure_mod017_h2h as h2h
import measure_mod017_lookup as lookup
import measure_mod017_transactions as tx
from mod017_index_support import configuration,evidence_run,validate_matrix,snapshot_catalog
from endpoints.schedule.read_repository import ScheduleReadRepository
from endpoints.scoring.weekly_repository import WeeklyCompletionRepository

CONFIGS={'ownership_game':[(),('team',),('member',),('game',),('team','game'),('member','game')],
         'transactions':[(),('pending',),('status',),('time',),('pending','status'),('pending','time')]}

def capture(name,family,callback,expected=None,values=None):
    c=tx.Capture();callback(c)
    return dict(name=name,family=family,sql=c.statement,params=c.params,expected_rows=expected,expected_values=values)

def group_cases(n,anchor):
    league=n//2+1;first=(league-1)*8+1;repo=ScheduleReadRepository();cases=[];clock=datetime.fromisoformat(anchor)
    for label,week,ids,lid in [('current',13,list(range(first,first+8)),league),('before',6,[first,first+1],league),('transfer',7,[first+1,first+2],league),('returned',10,[first,first+1],league),('unknown',13,[99999999],league),('absent',13,[first,first+1],n+100)]:
        values=[];start=clock+timedelta(days=(week-13)*7-1);end=start+timedelta(days=7)
        for i in range(1,h2h.games.game_facts(n)['games_per_season']+1):
            home,away,date=h2h.game_values(i,clock)
            hs=sorted(m for m in ids if home in h2h.owned(m,lid,week,n));aws=sorted(m for m in ids if away in h2h.owned(m,lid,week,n))
            if start<=date<=end and any(a!=b for a in hs for b in aws):
                values.append(dict(id=i,externalGameId=f'season-2026-game-{i:06d}',date=date,homeTeamId=home,awayTeamId=away,homeScore=i%45,awayScore=i%40,homeMemberIds=hs,awayMemberIds=aws))
        values.sort(key=lambda r:(r['date'],r['externalGameId']))
        p=dict(leagueId=lid,weekNumber=week,memberIds=ids)
        cases.append(capture('h2h_group_'+label,'group_h2h',lambda c,p=p:repo.head_to_head_games_for_members(c,p),len(values),values))
    return cases

def ownership_cases(n,anchor):
    cases=base.capture_queries(n);league=n//2+1;member=(league-1)*8+1;repo=ScheduleReadRepository()
    cases+=group_cases(n,anchor)
    cases+=lookup.capture_queries(n)[3:]
    for c in cases:
        if c['family']=='own':
            c['expected_rows']=n if c['name']=='own_hot_all' else n-n//3 if c['name']=='own_hot_active' else n//3 if c['name']=='own_hot_completed' else 1 if c['name']=='own_sparse_all' else 0
        if c['family']=='ownership':c['expected_rows']=0 if c['name'].split('ownership_')[1] in ('absent_team','wrong_member','null_member','before_acquisition') else 1
    for label,year in [('current',2026),('history',2025)]:
        p=dict(leagueId=league,sport=1,seasonYear=year,weekNumber=13)
        cases.append(capture('lookup_'+label,'lookup',lambda c,p=p:repo.search_teams(c,p),512))
    for label,user,scope in [('hot',1,list(range(1,n+1))),('sparse',2,[1]),('miss',2,[2])]:
        cases.append(capture('own_supplied_'+label,'own',lambda c,u=user,s=scope:base.LeagueReadRepository().own_leagues(c,u,'all',s),n if label=='hot' else 1 if label=='sparse' else 0))
    clock=datetime.fromisoformat(anchor);count=h2h.games.game_facts(n)['games_per_season']
    for label,method,p,teams,window,season in [
        ('member_current',repo.member_games,dict(leagueId=league,weekNumber=13,memberId=member),{1,2,3,4},(-1,6),2026),
        ('member_history',repo.member_games,dict(leagueId=league,weekNumber=6,memberId=member),{1,2,3,4},(-50,-43),2026),
        ('team_season',repo.team_season_games,dict(sportTeamId=1,seasonYear=2026,leagueId=league,weekNumber=13),{1},None,2026),
        ('conference',repo.conference_games,dict(sportConferenceId=2,seasonYear=2026,leagueId=league,weekNumber=13,weekStart=clock-timedelta(days=1),weekEnd=clock+timedelta(days=6)),set(range(17,33))|{1},(-1,6),2026)]:
        expected=sum(1 for i in range(1,count+1) if (lambda h,a,d:(h in teams or a in teams) and (window is None or clock+timedelta(days=window[0])<=d<=clock+timedelta(days=window[1])))(*h2h.game_values(i,clock)))
        cases.append(capture(label,'schedule',lambda c,p=p,m=method:m(c,p),expected))
    # Lookup fixture's historical count cases use the next league's default season.
    return cases

def normalized(case,rows):
    if case['family']=='group':return sorted(rows,key=lambda r:r['sportConferenceId'])
    if case['family']=='own':return sorted(rows,key=lambda r:(r['leagueId'],r['draftOrder'],base.canonical(r)))
    return rows

def statement_for(case):
    statement=text(case['sql'].replace('(__[POSTCOMPILE_scope_ids])', ':scope_ids'));params=case['params']
    if 'scope_ids' in params:statement=statement.bindparams(bindparam('scope_ids',expanding=True))
    return statement

def measure(conn,case):
    statement=statement_for(case);params=case['params']
    # Compile expanding own-list parameters before EXPLAIN, preserving canonical SQL.
    compiled=statement.params(**params).compile(dialect=conn.dialect,compile_kwargs={'render_postcompile':True})
    conn.execute(statement,params).fetchall()
    plan=conn.exec_driver_sql('EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) '+str(compiled),compiled.params).scalar_one()[0]
    samples=[];sig=None
    for _ in range(5):
        start=time.perf_counter();rows=[dict(r) for r in conn.execute(statement,params).mappings()];samples.append((time.perf_counter()-start)*1000)
        ordered_keys=base.signature([(r['leagueId'],r['draftOrder']) for r in rows]) if case['family']=='own' else None
        if case['family']=='own':
            expected_points=384 if params['user_id']==1 else 336
            if any(r['seasonPoints']!=expected_points for r in rows):raise AssertionError('Own score fixture changed')
        rows=normalized(case,rows)
        if case.get('expected_rows') is not None and len(rows)!=case['expected_rows']:raise AssertionError(f'{case["name"]}: expected {case["expected_rows"]}, got {len(rows)}')
        if case.get('expected_values') is not None:base.assert_equivalent(base.signature(case['expected_values']),base.signature(rows))
        if case['family']=='lookup':
            one=next(r for r in rows if r['teamId']==1)
            if (one['ownerTeamName'],one['ownerDisplayName'])!=('Team 1','User 1'):raise AssertionError('Owner labels changed')
        current=base.signature(rows)
        if ordered_keys is not None:current['ordered_keys']=ordered_keys
        if sig is not None:base.assert_equivalent(sig,current)
        sig=current
    return dict(name=case['name'],family=case['family'],sql=case['sql'],params=params,result=sig,samples=samples,median_ms=statistics.median(samples),plan=plan)

def transaction_cases(n,anchor,density,backlog):
    cases=tx.capture_queries(n,anchor);pending=1 if density==.001 else int(density*100)
    for c in cases:
        if c['name']=='list_pending':c['expected_rows']=pending
        if c['name']=='list_proposed':c['expected_rows']=19 if density==.001 else sum(1 for i in range(1,100) if i%5==0 and i>pending)
        if c['family']=='open':c['expected_rows']=0 if c['name'] in ('open_denied','open_missing_league') else (10 if density==.001 else sum(1 for i in range(1,101) if i%2==0 and (i<=pending or (i<100 and i%5==0))))
        if c['family']=='weekly':c['expected_rows']=n if backlog or density>.001 else n//10 if density==.001 else 0
    league=(n//20)*10
    for label,lid in [('pending_workflow',league),('pending_absent',n+100)]:
        cases.append(capture(label,'workflow',lambda c,l=lid:WeeklyCompletionRepository().pending(c,l),pending if lid==league else 0))
    return cases

def prepare_density(conn,n,density,backlog):
    conn.execute(text('''UPDATE "Transaction" SET status=CASE
      WHEN :density=0.001 AND id%100=0 AND "leagueId"%10=0 THEN 'PENDING_APPLY'
      WHEN :density>0.001 AND 1+(id-1)%100<=:pending THEN 'PENDING_APPLY'
      WHEN 1+(id-1)%100<100 AND (1+(id-1)%100)%5=0 THEN 'PROPOSED'
      WHEN (1+(id-1)%100)%3=0 THEN 'CANCELLED' ELSE 'COMPLETED' END'''),dict(density=density,pending=int(density*100)))
    conn.execute(text('UPDATE "Week" SET "scoringComplete"=("weekNumber">:backlog)'),dict(backlog=backlog))
    conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()
    statuses=[dict(r) for r in conn.exec_driver_sql('SELECT status,count(*) FROM "Transaction" GROUP BY status ORDER BY status').mappings()]
    pending=sum(r['count'] for r in statuses if r['status']=='PENDING_APPLY')
    if pending!=int(n*100*density):raise AssertionError('Prepared density mismatch')
    return dict(statuses=statuses,pending_fraction=density,unclosed_weeks=conn.exec_driver_sql('SELECT count(*) FROM "Week" WHERE NOT "scoringComplete"').scalar_one(),backlog_per_league=backlog)

def run_tier(admin,n,family,report):
    record=None
    try:
        with base.owned_database(admin) as name:
            record=dict(name=name,cleanup='pending');report['databases'].append(record)
            engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
            try:
                with engine.connect() as conn:
                    base.schema(conn);facts=base.seed(conn,n);anchor=facts['anchor']
                    if family=='ownership_game':
                        facts['games']=h2h.seed_head_to_head(conn,n,anchor)
                        conn.exec_driver_sql(f'UPDATE "League" SET "seasonYear"=2025 WHERE id={n//2+2}');conn.commit()
                        scenarios=[('default',None,None)]
                    else:
                        facts['transactions']=tx.seed_transactions(conn,n,anchor)
                        scenarios=[(f'density_{d}_backlog_{b}',d,b) for d in (.001,.1,.5) for b in (1,12)]+[('empty_pending_and_backlog',0,0)]
                    result=dict(size=n,family=family,fixture=facts,baseline_catalog=snapshot_catalog(conn),settings={k:conn.exec_driver_sql('SHOW '+k).scalar_one() for k in ['server_version','TimeZone','shared_buffers','work_mem','jit','max_parallel_workers_per_gather','statement_timeout','lock_timeout']},scenarios=[])
                    report['tiers'].append(result)
                    for label,density,backlog in scenarios:
                        prepared=prepare_density(conn,n,density,backlog) if density is not None else {}
                        cases=ownership_cases(n,anchor) if family=='ownership_game' else transaction_cases(n,anchor,density,backlog)
                        configs=CONFIGS[family] if n==1000 else ([(),('member',),('member','game')] if family=='ownership_game' else [(),('pending',),('status',),('time',),('pending','status')])
                        # Dense boundary screening needs partial only; history alternatives screened at sparse+small backlog.
                        if family=='transactions' and (density,backlog)!=(.001,1):configs=[(),('pending',)]
                        scenario=dict(name=label,prepared=prepared,records=[],builds={},catalog_restored=False);result['scenarios'].append(scenario);baseline={}
                        chosen=[c for c in cases if not (c['family']=='open' and (density,backlog)!=(.001,1))]
                        expected=[('+'.join(keys) or 'baseline',c['name']) for keys in configs for c in chosen]
                        for keys in configs:
                            config='+'.join(keys) or 'baseline'
                            print(f'{family} {n} {label} {config}',flush=True)
                            with configuration(conn,keys) as builds:
                                scenario['builds'][config]=builds
                                for case in chosen:
                                    r=measure(conn,case);r['configuration']=config
                                    if not keys:baseline[r['name']]=r['result']
                                    else:
                                        if baseline[r['name']]!=r['result']:raise AssertionError('Configuration parity: '+config+' / '+r['name'])
                                    scenario['records'].append(r)
                            scenario['catalog_restored']=True
                        validate_matrix(scenario['records'],expected);scenario['expected_matrix']=expected
                    return result
            finally:engine.dispose()
    finally:
        if record is not None:tx.verify_cleanup(admin,record)

def run(directory=None,families=('ownership_game','transactions'),connect=None,sizes=(1000,100,5000)):
    if any(f not in CONFIGS for f in families) or any(n not in base.SIZES for n in sizes) or not families or not sizes:raise ValueError('Unknown/empty matrix')
    directory=Path(directory or base.ROOT/'docs/modernization/baselines/mod-017-index-selection')
    sources=[Path(__file__),Path(__file__).with_name('mod017_index_support.py')]+[base.ROOT/p for p in [base.BASELINE,*base.MIGRATIONS,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_h2h.py','scripts/modernization/measure_mod017_games.py','scripts/modernization/measure_mod017_lookup.py','scripts/modernization/measure_mod017_transactions.py','api/endpoints/schedule/read_repository.py','api/endpoints/transaction/repository.py','api/endpoints/transaction/workflow_repository.py','api/endpoints/scoring/weekly_repository.py','api/endpoints/league/reads/repository.py','api/utils/ownership_reads.py']]
    with evidence_run(directory,sources) as report:
        report.update(requested_families=families,requested_sizes=sizes,scope='Controlled warm local read comparisons; no production recommendation or rollout')
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        try:
            for family in families:
                for n in sizes:run_tier(admin,n,family,report)
            if len(report['tiers'])!=len(families)*len(sizes) or any(r['cleanup']!='removed' for r in report['databases']):raise RuntimeError('Incomplete matrix/cleanup')
            report.update(result='PASS',cleanup='verified')
        finally:admin.close()
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--family',choices=CONFIGS,action='append');parser.add_argument('--size',type=int,choices=base.SIZES,action='append');parser.add_argument('--directory');args=parser.parse_args()
    run(args.directory,args.family or tuple(CONFIGS),sizes=tuple(args.size or (1000,100,5000)))
