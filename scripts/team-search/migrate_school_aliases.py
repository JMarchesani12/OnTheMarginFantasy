"""Create/seed only SchoolAlias on the explicitly identified configured project.

Default is a rollback-only dry run. --apply commits this additive transaction.
Never imports app/runtime, logs credentials, or rewrites school/team records.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'api'))
from utils.school_alias_seed import import_school_aliases


def run(apply, expected_target):
    values={**dotenv_values(ROOT/'api/.env'),**os.environ}
    url=make_url(values['SUPABASE_DB_URL']); project=values['SUPABASE_PROJECT_ID']
    if not project or not (project in (url.host or '') or (url.username or '').endswith('.'+project)):
        raise ValueError('Configured project identity mismatch')
    if any(key in url.query for key in ('service','hostaddr','host','port','user','password','dbname')):
        raise ValueError('Ambiguous connection transport')
    port=url.port or 5432
    if 'pooler' in (url.host or '') and port==6543: port=5432
    fingerprint=hashlib.sha256(f'{url.host}:{port}/{url.database}/{project}'.encode()).hexdigest()[:16]
    if fingerprint!=expected_target: raise ValueError('Target fingerprint mismatch')
    engine=create_engine(url.set(port=port),connect_args={'sslmode':'require','connect_timeout':8},pool_pre_ping=True)
    seed=json.loads((ROOT/'api/data/team_search_aliases.json').read_text())
    receipt={'targetFingerprint':fingerprint,'mode':'apply' if apply else 'dry-run'}
    try:
        with engine.connect() as conn:
            transaction=conn.begin()
            try:
                conn.execute(text("SET LOCAL lock_timeout='5s'"))
                conn.execute(text("SET LOCAL statement_timeout='60s'"))
                conn.execute(text('SELECT pg_advisory_xact_lock(71920261119)'))
                before=conn.execute(text('SELECT (SELECT count(*) FROM public."School") AS schools,(SELECT count(*) FROM public."SportTeam") AS teams')).mappings().one()
                exists=conn.execute(text('SELECT to_regclass(\'public."SchoolAlias"\') IS NOT NULL')).scalar_one()
                if not exists:
                    conn.exec_driver_sql((ROOT/'api/migrations/20261119_school_alias.sql').read_text())
                columns=set(conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='SchoolAlias'")).scalars())
                if columns!={'id','schoolId','alias','normalizedAlias','source','createdAt'}:
                    raise ValueError('Existing alias schema drift')
                constraints=set(conn.execute(text('SELECT conname FROM pg_constraint WHERE conrelid=\'public."SchoolAlias"\'::regclass')).scalars())
                if 'SchoolAlias_school_normalized_key' not in constraints: raise ValueError('Alias uniqueness missing')
                count_before=conn.execute(text('SELECT count(*) FROM public."SchoolAlias"')).scalar_one()
                receipt.update(import_school_aliases(conn,seed))
                count_after=conn.execute(text('SELECT count(*) FROM public."SchoolAlias"')).scalar_one()
                after=conn.execute(text('SELECT (SELECT count(*) FROM public."School") AS schools,(SELECT count(*) FROM public."SportTeam") AS teams')).mappings().one()
                if dict(before)!=dict(after): raise ValueError('School/team counts changed')
                northern=conn.execute(text('''SELECT st.id FROM public."SportTeam" st JOIN public."SchoolAlias" sa
                    ON sa."schoolId"=st."schoolId" WHERE st."externalId"='2460' AND sa."normalizedAlias"='northern iowa' ORDER BY st.id''')).scalars().all()
                if not northern: raise ValueError('Northern Iowa mapping verification failed')
                # Replay must be idempotent and retain aliases/sources already present.
                import_school_aliases(conn,seed)
                if conn.execute(text('SELECT count(*) FROM public."SchoolAlias"')).scalar_one()!=count_after:
                    raise ValueError('Alias import is not idempotent')
                receipt.update(aliasCount=count_after,inserted=count_after-count_before,schoolCount=after['schools'],teamCount=after['teams'],northernIowaTeamIds=northern)
                if apply: transaction.commit()
                else: transaction.rollback()
            except BaseException:
                transaction.rollback()
                raise
        if apply:
            with engine.connect() as conn:
                committed=conn.execute(text('SELECT count(*) FROM public."SchoolAlias"')).scalar_one()
                if committed!=receipt['aliasCount']: raise ValueError('Committed alias count verification failed')
        receipt['result']='APPLIED_AND_VERIFIED' if apply else 'DRY_RUN_ROLLED_BACK'
        return receipt
    finally:
        engine.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-target',required=True)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args()
    try:
        receipt=run(args.apply,args.expected_target)
    except Exception as error:
        print(json.dumps({'result':'FAILED','category':type(error).__name__}))
        return 1
    args.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt))
    return 0


if __name__=='__main__': raise SystemExit(main())
