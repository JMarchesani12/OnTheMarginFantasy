"""Private fixture index registry and fail-closed evidence/catalog contracts."""
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import time
from uuid import uuid4

PREFIX='mod017_final_'
CANDIDATES={
 'team':('LeagueTeamSlot','("leagueId","sportTeamId") INCLUDE ("memberId","acquiredWeek","droppedWeek")'),
 'member':('LeagueTeamSlot','("leagueId","memberId","sportTeamId") INCLUDE ("acquiredWeek","droppedWeek")'),
 'game':('GameResult','("sportSeasonId",date,"externalGameId")'),
 'pending':('Transaction','("leagueId",id) WHERE status=\'PENDING_APPLY\''),
 'status':('Transaction','("leagueId",status,"createdAt" DESC,id DESC)'),
 'time':('Transaction','("leagueId","createdAt" DESC,id DESC) INCLUDE (status)'),
}
SIGNATURE_FIELDS=('schema','table_name','method','key_definitions','includes','operator_classes','collations','options','predicate','valid','ready','unique','primary','exclusion','nulls_not_distinct','constraints')

def index_signature(row):
    return json.dumps({k:row[k] for k in SIGNATURE_FIELDS},sort_keys=True)

def equivalent_indexes(candidate,rows):
    signature=index_signature(candidate)
    return [r for r in rows if index_signature(r)==signature]

def snapshot_catalog(conn):
    return [dict(r) for r in conn.exec_driver_sql('''SELECT i.oid::bigint AS oid,i.relname AS name,ns.nspname AS schema,t.relname AS table_name,
      am.amname AS method,x.indisunique AS unique,x.indisprimary AS primary,x.indisexclusion AS exclusion,
      x.indisvalid AS valid,x.indisready AS ready,x.indnullsnotdistinct AS nulls_not_distinct,
      ARRAY(SELECT pg_get_indexdef(i.oid,k,true) FROM generate_series(1,x.indnkeyatts) k) AS key_definitions,
      ARRAY(SELECT pg_get_indexdef(i.oid,k,true) FROM generate_series(x.indnkeyatts+1,x.indnatts) k) AS includes,
      x.indclass::text AS operator_classes,x.indcollation::text AS collations,x.indoption::text AS options,
      pg_get_expr(x.indpred,x.indrelid) AS predicate,
      ARRAY(SELECT c.conname FROM pg_constraint c WHERE c.conindid=i.oid ORDER BY c.conname) AS constraints,
      pg_get_indexdef(i.oid) AS definition,pg_relation_size(i.oid) AS bytes
      FROM pg_index x JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_class t ON t.oid=x.indrelid
      JOIN pg_namespace ns ON ns.oid=t.relnamespace JOIN pg_am am ON am.oid=i.relam
      WHERE ns.nspname='public' ORDER BY t.relname,i.relname''').mappings()]

def assert_owned_index(row,owned):
    if (not row['name'].startswith(PREFIX) or owned.get(row['name'])!=row['oid'] or row['constraints'] or row['primary'] or row['exclusion']):
        raise RuntimeError('Refusing teardown of unowned or integrity index')

def catalog_identity(rows):
    return [(r['oid'],r['name'],index_signature(r)) for r in rows]

@contextmanager
def configuration(conn,keys):
    baseline=snapshot_catalog(conn);owned={};builds=[]
    try:
        for key in keys:
            table,columns=CANDIDATES[key];name=PREFIX+key
            if any(r['name']==name for r in baseline):raise RuntimeError('Fixture candidate name already exists')
            start=time.perf_counter()
            conn.exec_driver_sql(f'CREATE INDEX "{name}" ON public."{table}" {columns}')
            row=next(r for r in snapshot_catalog(conn) if r['name']==name)
            owned[name]=row['oid']
            equivalents=equivalent_indexes(row,baseline)
            if equivalents:raise RuntimeError('Equivalent baseline index: '+str([r['name'] for r in equivalents]))
            builds.append(dict(key=key,build_ms=(time.perf_counter()-start)*1000,catalog=row))
        conn.commit();conn.exec_driver_sql('ANALYZE');conn.commit()
        yield builds
    finally:
        conn.rollback()
        for row in snapshot_catalog(conn):
            if row['name'] in owned:
                assert_owned_index(row,owned)
                conn.exec_driver_sql(f'DROP INDEX public."{row["name"]}"')
        conn.commit()
        if catalog_identity(snapshot_catalog(conn))!=catalog_identity(baseline):raise RuntimeError('Baseline catalog not restored')

def validate_matrix(records,expected):
    actual=[(r['configuration'],r['name']) for r in records]
    if len(actual)!=len(set(actual)) or set(actual)!=set(expected):raise AssertionError('Incomplete/duplicate configuration matrix')
    if any(len(r['samples'])!=5 for r in records):raise AssertionError('Incomplete samples')

def save_json(path,value):
    path=Path(path);tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2,default=str)+'\n');tmp.replace(path)

@contextmanager
def evidence_run(directory,sources):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    artifact=directory/f'mod-017-indexes-{uuid4().hex}.json'
    report=dict(result='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),provenance={},databases=[],cleanup='no database created',tiers=[])
    def persist():
        save_json(artifact,report);save_json(directory/'current.json',dict(result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist()
    try:
        report['provenance']={str(p):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources}
        yield report
        if report['result']!='PASS':raise RuntimeError('Run did not prove completion')
    except BaseException as error:
        report.update(result='FAILED',error_type=type(error).__name__,error=str(error));raise
    finally:
        if report['databases']:
            report['cleanup']='verified' if all(r.get('cleanup')=='removed' for r in report['databases']) else 'unverified'
            if report['result']=='PASS' and report['cleanup']!='verified':report['result']='FAILED'
        persist()
