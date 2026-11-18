"""Actual public search contract on marked synthetic PostgreSQL; no configured DSN."""
from datetime import datetime,timezone
import hashlib
from pathlib import Path
from uuid import uuid4
import psycopg2
from sqlalchemy import create_engine,text
import measure_mod017 as base
import measure_mod018_search as fixtures
from measure_mod017_transactions import save_json,verify_cleanup
from endpoints.league.reads.service import LeagueReadService


def checks(engine):
    service=LeagueReadService(engine);walks=[];boundaries=[];mixed=[];n=1000
    with engine.connect() as conn:
        base.schema(conn);facts=fixtures.seed(conn,n);before_catalog=base.catalog(conn);conn.commit()
        for layout in ['original','descending_heap']:
            if layout=='descending_heap':
                conn.exec_driver_sql('CREATE INDEX mod018_order_heap ON "League" (id DESC)');conn.exec_driver_sql('CLUSTER "League" USING mod018_order_heap');conn.exec_driver_sql('DROP INDEX mod018_order_heap');conn.exec_driver_sql('ANALYZE');conn.commit()
            for sport in [None,1,2]:
                wanted=fixtures.eligible_ids(n,sport)
                for limit in [6,20,50]:
                    ids=[];pages=[]
                    for offset in range(0,len(wanted),limit):
                        rows=service.search_public('Audit League',sport,limit,offset)
                        case=dict(sport=sport,expected_rows=min(limit,len(wanted)-offset),params=dict(q='Audit League',limit=limit,offset=offset))
                        fixtures.validate_rows(n,case,rows)
                        current=[r['id'] for r in rows];ids.extend(current);pages.append(dict(offset=offset,ids=current,result=base.signature(rows)))
                    walks.append(dict(layout=layout,sport=sport,limit=limit,pages=pages,expected_ids=wanted,returned_ids=ids,duplicates=len(ids)-len(set(ids)),missing_ids=sorted(set(wanted)-set(ids)),ordered_complete=ids==wanted))
                    for name,offset,q in [('terminal',len(wanted)-1,'Audit League'),('exhausted',len(wanted),'Audit League'),('max_offset',10000,'Audit League'),('miss',0,'Absent'),('short',0,'a')]:
                        rows=service.search_public(q,sport,limit,offset);expected=[fixtures.expected_row(wanted[-1])] if name=='terminal' else []
                        match=base.signature(rows)==base.signature(expected)
                        # Terminal selection is also an ordering check: preserve failures
                        # until the run ends so RED evidence retains every layout/case.
                        if name!='terminal':base.assert_equivalent(base.signature(expected),base.signature(rows))
                        boundaries.append(dict(layout=layout,sport=sport,limit=limit,name=name,expected=base.signature(expected),actual=base.signature(rows),matched=match))
        after_catalog=base.catalog(conn)
        if fixtures.structural_catalog(before_catalog)!=fixtures.structural_catalog(after_catalog):raise AssertionError('Fixture layout changed index definitions')
        # Separate names exercise similarity before name/ID, not only tied pages.
        named=[(1001,'Margin',1,True),(1002,'Margin AA',1,True),(1003,'Margin BB',1,True),(1004,'Margin',1,True),(1005,'Margin Hidden',1,False),(1006,'Unrelated',1,True),(1007,'Margin',2,True)]
        for i,name,sport,visible in named:
            conn.execute(text('''INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear","isDiscoverable") VALUES (:id,:name,:sport,8,'Pre-Draft','{}',1,2026,:visible)'''),dict(id=i,name=name,sport=sport,visible=visible))
        conn.commit()
        for sport,wanted in [(None,[1001,1004,1007,1002,1003]),(1,[1001,1004,1002,1003]),(2,[1007])]:
            rows=service.search_public('Margin',sport,50,0);by_id={i:(name,s) for i,name,s,v in named if v};expected=[dict(fixtures.expected_row(i),name=by_id[i][0],sport=by_id[i][1]) for i in wanted]
            mixed.append(dict(sport=sport,expected_ids=wanted,actual_ids=[r['id'] for r in rows],actual=base.signature(rows),expected=base.signature(expected),matched=base.signature(rows)==base.signature(expected)))
    return dict(fixture=facts,page_sizes=[6,20,50],walks=walks,boundaries=boundaries,mixed_name_cases=mixed,index_definitions_preserved=True,production_sql=fixtures.capture_queries(n)[0]['sql'])


def run(directory=None,connect=None):
    directory=Path(directory or base.ROOT/'docs/modernization/evidence');directory.mkdir(parents=True,exist_ok=True);run_id=uuid4().hex;artifact=directory/f'mod-018-search-order-{run_id}.json';manifest=directory/'mod-018-search-order-current-2026-11-16.json'
    report=dict(date='2026-11-16',run_id=run_id,result='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),provenance={},database=None,cleanup='no database created',checks=None)
    def persist():save_json(artifact,report);save_json(manifest,dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        inputs=[base.BASELINE,*base.MIGRATIONS,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod018_search.py','scripts/modernization/verify_mod018_search_order.py','api/endpoints/league/reads/repository.py','api/endpoints/league/reads/service.py','api/endpoints/league/leagueEndpoints.py','api/utils/authorization.py','api/utils/conference_membership.py']
        report['provenance']={name:hashlib.sha256((base.ROOT/name).read_bytes()).hexdigest() for name in inputs}
        admin=connect() if connect else psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        try:
            with base.owned_database(admin) as name:
                report['database']=dict(name=name,cleanup='pending');report['cleanup']='pending';persist()
                engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
                try:report['checks']=checks(engine)
                finally:engine.dispose()
        finally:
            if report['database'] is not None:
                verify_cleanup(admin,report['database']);report['cleanup']='verified' if report['database']['cleanup']=='removed' else 'unverified'
        data=report['checks'];failed_walks=sum(not w['ordered_complete'] for w in data['walks']);failed_boundaries=sum(not x['matched'] for x in data['boundaries']);failed_mixed=sum(not x['matched'] for x in data['mixed_name_cases']);report['failures']=dict(walks=failed_walks,boundaries=failed_boundaries,mixed=failed_mixed)
        if failed_walks or failed_boundaries or failed_mixed:raise AssertionError('Public search order contract failed')
        if report['cleanup']!='verified':raise AssertionError('Owned cleanup unverified')
        report['result']='PASS';return report
    except BaseException as error:report['result']='FAILED';report['error_type']=type(error).__name__;raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();persist()
        if admin is not None:admin.close()
if __name__=='__main__':run();print('Actual public search order contract PASS:6/20/50,filters,layouts,fullpayloads')
