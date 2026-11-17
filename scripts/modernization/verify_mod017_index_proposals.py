"""Execute proposal safety cases only on UUID-owned marked localhost databases."""
from pathlib import Path
import json
import re
import subprocess
import psycopg2
from sqlalchemy import create_engine
import measure_mod017 as base
import measure_mod017_transactions as tx
from mod017_index_support import evidence_run,snapshot_catalog,catalog_identity
PACKAGE=base.ROOT/'docs/modernization/proposals/mod-017-indexes'


def fixture_container():
    result=subprocess.run(['docker','ps','--filter','label=otm.task=mod017-final','--format','{{.ID}}'],text=True,capture_output=True,check=True)
    ids=result.stdout.split()
    if len(ids)!=1:raise RuntimeError('Expected exactly one task-owned fixture container')
    row=json.loads(subprocess.check_output(['docker','inspect',ids[0]],text=True))[0]
    if row['Image']!='sha256:00bc86618629af00d2937fdc5a5d63db3ff8450acf52f0636ec813c7f4902929' or row['Config']['Labels'].get('otm.synthetic')!='true' or row['Mounts']:raise RuntimeError('Wrong fixture image/labels/mounts')
    return row['Id']

def expand_includes(script):
    return re.sub(r'^\\ir ([a-z]+\.sql)$',lambda m:expand_includes((PACKAGE/m[1]).read_text()),script,flags=re.MULTILINE)

def psql(name,script):
    return subprocess.run(['docker','exec','-i',fixture_container(),'psql','-X','-U','postgres','-d',name,'-v','ON_ERROR_STOP=1'],input=expand_includes(script),text=True,capture_output=True,timeout=30)

def run(directory=None):
    sources=[Path(__file__),Path(__file__).with_name('mod017_index_support.py')]+list(PACKAGE.glob('*.sql'))+[base.ROOT/base.BASELINE,*[base.ROOT/p for p in base.MIGRATIONS]]
    with evidence_run(directory or base.ROOT/'docs/modernization/baselines/mod-017-index-selection/proposals',sources) as report:
        report['cases']=[];admin=psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        try:
            for case in ['missing','create_verify_recover','equivalent_other_name','equivalent_same_name','constraint_equivalent','constraint_same_name','same_name_drift','invalid','recovery_drift']:
                record=None
                try:
                    with base.owned_database(admin) as name:
                        record=dict(name=name,cleanup='pending');report['databases'].append(record)
                        engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
                        blocker=None
                        try:
                            with engine.connect() as conn:
                                if case!='missing':base.schema(conn)
                                baseline=snapshot_catalog(conn);conn.commit()
                                if case in ['equivalent_other_name','equivalent_same_name']:
                                    index='existing_equivalent' if case.endswith('other_name') else 'mod017_owner_member_team'
                                    conn.exec_driver_sql(f'CREATE INDEX "{index}" ON "LeagueTeamSlot" ("leagueId","memberId","sportTeamId") INCLUDE ("acquiredWeek","droppedWeek")');conn.commit()
                                elif case in ['constraint_equivalent','constraint_same_name']:
                                    index='fixture_constraint' if case=='constraint_equivalent' else 'mod017_owner_member_team'
                                    conn.exec_driver_sql(f'ALTER TABLE "LeagueTeamSlot" ADD CONSTRAINT "{index}" UNIQUE ("leagueId","memberId","sportTeamId") INCLUDE ("acquiredWeek","droppedWeek")');conn.commit()
                                elif case=='same_name_drift':
                                    conn.exec_driver_sql('CREATE INDEX mod017_owner_member_team ON "LeagueTeamSlot" ("leagueId")');conn.commit()
                                elif case=='invalid':
                                    blocker=psycopg2.connect(dbname=name,**base.LOCAL)
                                    with blocker.cursor() as cursor:cursor.execute('UPDATE "LeagueTeamSlot" SET "acquiredWeek"=1')
                                    interrupted=psql(name,'SET statement_timeout=200; CREATE INDEX CONCURRENTLY fixture_invalid ON "LeagueTeamSlot" ("acquiredWeek");')
                                    if interrupted.returncode==0:raise AssertionError('Expected concurrent build interruption')
                                    blocker.rollback();blocker.close();blocker=None
                                    invalid=next(r for r in snapshot_catalog(conn) if r['name']=='fixture_invalid');conn.commit()
                                    if invalid['valid']:raise AssertionError('Expected native invalid residual')
                                before=catalog_identity(snapshot_catalog(conn));conn.commit()
                                script='\\ir create.sql\n\\ir verify.sql\n'
                                if case=='recovery_drift':script+='ALTER INDEX public.mod017_owner_member_team RENAME TO fixture_drift;\n'
                                if case in ['create_verify_recover','equivalent_other_name','equivalent_same_name','constraint_equivalent','recovery_drift']:
                                    script+='\\set mod017_recovery_approved true\n\\ir recovery.sql\n'
                                result=psql(name,script);after=snapshot_catalog(conn);conn.commit()
                                should_pass=case in ['create_verify_recover','equivalent_other_name','equivalent_same_name','constraint_equivalent']
                                if not should_pass and 'REFUSE:' not in result.stdout:raise AssertionError('Failure was not an intended safety refusal: '+result.stderr+result.stdout)
                                if (result.returncode==0)!=should_pass:raise AssertionError(f'{case}: unexpected psql exit {result.returncode}: '+result.stderr+result.stdout)
                                if case=='recovery_drift':
                                    if 'fixture_drift' not in {r['name'] for r in after} or any((oid,name,sig) not in catalog_identity(after) for oid,name,sig in before):raise AssertionError('Recovery drift removed renamed/baseline index')
                                elif catalog_identity(after)!=before:raise AssertionError(case+': unexpected partial catalog mutation')
                                report['cases'].append(dict(name=case,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr,catalog_preserved=case!='recovery_drift',drift_preserved_owned_and_baseline=case=='recovery_drift'))
                                print('proposal '+case+' PASS',flush=True)
                        finally:
                            if blocker:blocker.rollback();blocker.close()
                            engine.dispose()
                finally:
                    if record:tx.verify_cleanup(admin,record)
            if len(report['cases'])!=9 or any(r['cleanup']!='removed' for r in report['databases']):raise RuntimeError('Incomplete proposal cases/cleanup')
            report.update(result='PASS',cleanup='verified')
        finally:admin.close()
    return report
if __name__=='__main__':run()
