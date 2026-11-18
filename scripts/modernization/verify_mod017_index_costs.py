"""Representative statement WAL/build probes; never whole-workflow cost claims."""
from datetime import datetime,timezone
from pathlib import Path
import threading
import time
import psycopg2
from sqlalchemy import create_engine,text
import measure_mod017 as base
import measure_mod017_h2h as h2h
import measure_mod017_transactions as tx
from mod017_index_support import CANDIDATES,configuration,evidence_run,snapshot_catalog,catalog_identity,assert_owned_index

PROBES=[
 ('game_insert','''INSERT INTO "GameResult" (id,sport,"externalGameId",date,"homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","sportSeasonId") SELECT :newgame,sport,'synthetic-cost-insert',date,"homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","sportSeasonId" FROM "GameResult" WHERE id=1'''),
 ('game_correction','UPDATE "GameResult" SET "homeScore"="homeScore"+1,date=date+interval \'1 second\' WHERE id=1'),
 ('ownership_drop','UPDATE "LeagueTeamSlot" SET "droppedWeek"=14 WHERE "leagueId"=:league AND "sportTeamId"=1 AND "droppedWeek" IS NULL'),
 ('ownership_acquire','''INSERT INTO "LeagueTeamSlot" (id,"leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") VALUES (:newslot,:league,:member,1,14,'FREE_AGENT')'''),
 ('transaction_insert','''INSERT INTO "Transaction" (id,"leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds") VALUES (:newtx,:league,:week,'TRADE',:member,:other,'PENDING_APPLY','[1]','[5]')'''),
 ('transaction_apply','UPDATE "Transaction" SET status=\'COMPLETED\' WHERE id=:pending'),
]

def probes(conn,n):
    league=(n//20)*10;member=(league-1)*8+1
    params=dict(league=league,member=member,other=member+1,week=(league-1)*13+13,pending=league*100,newgame=conn.exec_driver_sql('SELECT max(id)+1 FROM "GameResult"').scalar_one(),newslot=conn.exec_driver_sql('SELECT max(id)+1 FROM "LeagueTeamSlot"').scalar_one(),newtx=n*100+1)
    records=[]
    for iteration in range(5):
        transaction=conn.begin_nested()
        try:
            for name,sql in PROBES:
                start=time.perf_counter();plan=conn.execute(text('EXPLAIN (ANALYZE,BUFFERS,WAL,FORMAT JSON) '+sql),params).scalar_one()[0]
                records.append(dict(name=name,iteration=iteration,client_ms=(time.perf_counter()-start)*1000,plan=plan))
            checks=conn.execute(text('''SELECT
              (SELECT "homeScore" FROM "GameResult" WHERE id=1) AS score,
              (SELECT count(*) FROM "GameResult" WHERE id=:newgame) AS inserted,
              (SELECT count(*) FROM "LeagueTeamSlot" WHERE id=:newslot AND "acquiredWeek"=14) AS acquired,
              (SELECT status FROM "Transaction" WHERE id=:pending) AS applied,
              (SELECT status FROM "Transaction" WHERE id=:newtx) AS added'''),params).mappings().one()
            if dict(checks)!=dict(score=2,inserted=1,acquired=1,applied='COMPLETED',added='PENDING_APPLY'):raise AssertionError('Representative write result changed')
        finally:transaction.rollback()
    if conn.execute(text('SELECT status FROM "Transaction" WHERE id=:pending'),params).scalar_one()!='PENDING_APPLY':raise AssertionError('Rollback failed')
    return dict(mode='five savepoint rollbacks; physical dead entries/cache can accumulate',operations=records,parameters=params,correctness='checked each iteration and rollback')

def concurrent_probe(name,conn):
    baseline=snapshot_catalog(conn);conn.commit();index='mod017_final_concurrent';table,columns=CANDIDATES['game']
    ddl=f'CREATE INDEX CONCURRENTLY "{index}" ON public."{table}" {columns}'
    blocker=psycopg2.connect(dbname=name,**base.LOCAL);builder=psycopg2.connect(dbname=name,**base.LOCAL);builder.autocommit=True
    outcome={};thread=None
    try:
        with blocker.cursor() as cursor:cursor.execute('UPDATE "GameResult" SET "homeScore"="homeScore" WHERE id=1')
        with builder.cursor() as cursor:cursor.execute('SET statement_timeout=2000')
        def build():
            try:
                with builder.cursor() as cursor:cursor.execute(ddl)
                outcome['result']='unexpected success'
            except psycopg2.errors.QueryCanceled:outcome['result']='statement timeout'
            except BaseException as error:outcome['error']=repr(error)
        thread=threading.Thread(target=build);thread.start();deadline=time.monotonic()+4;observed=False
        while thread.is_alive() and time.monotonic()<deadline:
            row=conn.execute(text('SELECT wait_event_type,wait_event FROM pg_stat_activity WHERE pid=:pid'),dict(pid=builder.get_backend_pid())).mappings().one()
            conn.commit()
            if row['wait_event_type']=='Lock':observed=True
            time.sleep(.02)
        thread.join(1)
        if thread.is_alive() or outcome.get('result')!='statement timeout' or not observed:raise AssertionError('Concurrent blocker barrier/timeout not observed: '+repr(outcome))
        residual=next(r for r in snapshot_catalog(conn) if r['name']==index);conn.commit()
        if residual['valid']:raise AssertionError('Expected invalid interrupted build')
        owned={index:residual['oid']};assert_owned_index(residual,owned)
        blocker.rollback()
        with builder.cursor() as cursor:
            cursor.execute(f'DROP INDEX CONCURRENTLY public."{index}"')
            cursor.execute('SET statement_timeout=120000')
            start=time.perf_counter();cursor.execute(ddl);build_ms=(time.perf_counter()-start)*1000
        complete=next(r for r in snapshot_catalog(conn) if r['name']==index);conn.commit()
        if not complete['valid'] or not complete['ready'] or complete['constraints']:raise AssertionError('Concurrent build invalid')
        assert_owned_index(complete,{index:complete['oid']})
        with builder.cursor() as cursor:cursor.execute(f'DROP INDEX CONCURRENTLY public."{index}"')
        if catalog_identity(snapshot_catalog(conn))!=catalog_identity(baseline):raise AssertionError('Concurrent catalog not restored')
        return dict(blocker_observed=observed,interrupted=outcome,residual=residual,recovery='exact owned invalid index dropped concurrently; recreated and dropped valid index',complete=complete,concurrent_build_ms=build_ms,catalog_restored=True)
    finally:
        blocker.rollback();blocker.close()
        if thread and thread.is_alive():builder.cancel();thread.join(5)
        builder.close()

def run(directory=None,n=1000):
    sources=[Path(__file__),Path(__file__).with_name('mod017_index_support.py')]+[base.ROOT/p for p in [base.BASELINE,*base.MIGRATIONS,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_h2h.py','scripts/modernization/measure_mod017_games.py','scripts/modernization/measure_mod017_transactions.py']]
    with evidence_run(directory or base.ROOT/'docs/modernization/baselines/mod-017-index-selection/costs',sources) as report:
        admin=psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True;record=None
        try:
            try:
                with base.owned_database(admin) as name:
                    record=dict(name=name,cleanup='pending');report['databases'].append(record)
                    engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
                    try:
                        with engine.connect() as conn:
                            base.schema(conn);facts=base.seed(conn,n);h2h.seed_head_to_head(conn,n,facts['anchor']);tx.seed_transactions(conn,n,facts['anchor'])
                            report.update(scope='Direct representative SQL, not canonical whole-workflow throughput; WAL is statement-level, not per-index attribution',fixture=facts,configurations=[])
                            for keys in [(),('team',),('member',),('game',),('member','game'),('pending',),('status',),('time',),('pending','status')]:
                                print('costs '+('+'.join(keys) or 'baseline'),flush=True)
                                with configuration(conn,keys) as builds:
                                    report['configurations'].append(dict(configuration='+'.join(keys) or 'baseline',builds=builds,writes=probes(conn,n)))
                            report['concurrent']=concurrent_probe(name,conn)
                    finally:engine.dispose()
            finally:
                if record:tx.verify_cleanup(admin,record)
            if not record or record['cleanup']!='removed':raise RuntimeError('Owned database cleanup unverified')
            report.update(result='PASS',cleanup='verified')
        finally:admin.close()
    return report

if __name__=='__main__':run()
