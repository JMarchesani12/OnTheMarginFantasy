"""Preserve aliases and plan canonical names; stage column removal after deployment.

--plan is read-only. Default dry-run renames/drops inside a transaction, tests the
new read paths, then rolls everything back. --apply-names commits ONLY aliases
and canonical names, retaining both legacy columns. Destructive commit requires
--drop-retired-columns AND the operator's verified --deployed-revision.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from dotenv import dotenv_values
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'api'))
from utils.school_names import plan_school_names
from utils.team_search import normalize_team_search_text,rank_team_search_match


def configured_engine(expected_target):
    values={**dotenv_values(ROOT/'api/.env'),**os.environ};url=make_url(values['SUPABASE_DB_URL']);project=values['SUPABASE_PROJECT_ID']
    if not project or not (project in (url.host or '') or (url.username or '').endswith('.'+project)):
        raise ValueError('Configured project identity mismatch')
    if any(key in url.query for key in ('service','hostaddr','host','port','user','password','dbname')):
        raise ValueError('Ambiguous transport overrides')
    port=url.port or 5432
    if 'pooler' in (url.host or '') and port==6543:port=5432
    fingerprint=hashlib.sha256(f'{url.host}:{port}/{url.database}/{project}'.encode()).hexdigest()[:16]
    if fingerprint!=expected_target:raise ValueError('Target identity mismatch')
    return create_engine(url.set(port=port),connect_args={'sslmode':'require','connect_timeout':8},pool_pre_ping=True)


def verify_reads(conn):
    from endpoints.sport.repository import SportRepository
    from endpoints.league.reads.repository import LeagueReadRepository
    from endpoints.schedule.ingestion_repository import ScheduleIngestionRepository
    from endpoints.schedule.read_repository import ScheduleReadRepository
    from endpoints.draft.snapshot_repository import DraftSnapshotRepository
    from endpoints.roster.repository import RosterRepository
    from endpoints.transaction.repository import TransactionRepository
    from endpoints.transaction.workflow_repository import TransactionWorkflowRepository
    catalog=SportRepository().team_search_catalog(conn)
    northern=[row for row in catalog if row['teamId'] in (369,525)]
    if {row['teamName'] for row in northern}!={'Northern Iowa'}:raise ValueError('Canonical Northern Iowa name mismatch')
    aliases=[row['alias'] for row in northern if row['alias']]
    for query in ('UNI','Northern Iowa','University of Northern Iowa'):
        if not rank_team_search_match('Northern Iowa',query,aliases):raise ValueError('Preserved alias no longer matches')
    for sport in (1,2):
        LeagueReadRepository().rules_teams(conn,sport)
        ScheduleIngestionRepository().sport_teams(conn,{'sportId':sport}).fetchall()
    ScheduleReadRepository().search_teams(conn,dict(leagueId=-1,sport=1,seasonYear=2026,weekNumber=1)).fetchall()
    DraftSnapshotRepository().snapshot_picks(conn,-1)
    RosterRepository().member_teams(conn,-1,-1,1)
    RosterRepository().available_teams(conn,-1,1,2026,None,1)
    TransactionRepository().list_transactions(conn,-1)
    TransactionWorkflowRepository().open_trades(conn,dict(league_id=-1,member_id=-1)).fetchall()
    games=ScheduleReadRepository().team_season_games(conn,dict(sportTeamId=369,seasonYear=2026,leagueId=-1,weekNumber=1)).mappings().all()
    canonical={row['teamId']:row['teamName'] for row in catalog}
    for game in games:
        for side in ('home','away'):
            team_id=game[side+'TeamId']
            if team_id in canonical and game[side+'TeamName']!=canonical[team_id]:
                raise ValueError('Linked game label differs from canonical school name')
    return {'canonicalNamesVerified':True,'preservedSearchQueries':['UNI','Northern Iowa','University of Northern Iowa']}


def run(args):
    engine=configured_engine(args.expected_target)
    try:
        with engine.connect() as conn:
            tx=conn.begin()
            try:
                if args.plan:conn.execute(text('SET TRANSACTION READ ONLY'))
                conn.execute(text("SET LOCAL lock_timeout='3s'"));conn.execute(text("SET LOCAL statement_timeout='45s'"))
                if not args.plan:
                    conn.execute(text('SELECT pg_advisory_xact_lock(71920261119)'))
                    conn.execute(text('LOCK TABLE public."School",public."SchoolAlias",public."SportTeam" IN SHARE ROW EXCLUSIVE MODE'))
                schools=conn.execute(text('SELECT id,name FROM public."School" ORDER BY id')).mappings().all()
                teams=conn.execute(text('SELECT id,"schoolId","externalId" FROM public."SportTeam" ORDER BY id')).mappings().all()
                seed=json.loads((ROOT/'api/data/team_search_aliases.json').read_text())
                plan=plan_school_names(schools,teams,seed)
                receipt=dict(targetFingerprint=args.expected_target,schoolCount=len(schools),teamCount=len(teams),**plan)
                if args.plan:
                    tx.rollback();receipt['result']='READ_ONLY_PLAN';return receipt
                old_labels=[(row['id'],row['name']) for row in schools]
                columns=set(conn.execute(text("SELECT table_name||'.'||column_name FROM information_schema.columns WHERE table_schema='public' AND table_name IN ('School','SportTeam')")).scalars())
                if 'School.shortName' in columns:
                    old_labels += [(row[0],row[1]) for row in conn.execute(text('SELECT id,"shortName" FROM public."School" WHERE "shortName" IS NOT NULL'))]
                if 'SportTeam.displayName' in columns:
                    old_labels += [(row[0],row[1]) for row in conn.execute(text('SELECT "schoolId","displayName" FROM public."SportTeam"'))]
                existing_aliases=set(tuple(row) for row in conn.execute(text('SELECT "schoolId","normalizedAlias" FROM public."SchoolAlias"')))
                for school_id,label in old_labels:
                    normalized=normalize_team_search_text(label)
                    if not normalized:raise ValueError('Legacy label cannot be preserved')
                    if (school_id,normalized) in existing_aliases:continue
                    conn.execute(text('''INSERT INTO public."SchoolAlias" ("schoolId",alias,"normalizedAlias",source)
                        VALUES (:school,:alias,:normalized,'preserved before name consolidation')
                        ON CONFLICT ("schoolId","normalizedAlias") DO NOTHING'''),dict(school=school_id,alias=label,normalized=normalized))
                    existing_aliases.add((school_id,normalized))
                for row in plan['updates']:
                    conn.execute(text('UPDATE public."School" SET name=:newName WHERE id=:schoolId AND name=:oldName'),row)
                stored=set(tuple(row) for row in conn.execute(text('SELECT "schoolId","normalizedAlias" FROM public."SchoolAlias"')))
                if any((school_id,normalize_team_search_text(label)) not in stored for school_id,label in old_labels):
                    raise ValueError('Legacy alias preservation failed')
                if not args.apply_names:
                    conn.execute(text("SET LOCAL onthemargin.school_names_verified='true'"))
                    conn.exec_driver_sql((ROOT/'api/migrations/20261119_retire_school_name_columns.sql').read_text())
                receipt.update(verify_reads(conn))
                receipt['aliasCount']=conn.execute(text('SELECT count(*) FROM public."SchoolAlias"')).scalar_one()
                if args.apply_names or args.drop_retired_columns:
                    tx.commit();receipt['result']='NAMES_APPLIED_COLUMNS_RETAINED' if args.apply_names else 'COLUMNS_REMOVED'
                    if args.drop_retired_columns:receipt['deployedRevision']=args.deployed_revision
                else:
                    tx.rollback();receipt['result']='DRY_RUN_RENAMED_AND_DROPPED_ROLLED_BACK'
                return receipt
            except BaseException:
                tx.rollback();raise
    finally:engine.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-target',required=True);parser.add_argument('--receipt',type=Path,required=True)
    group=parser.add_mutually_exclusive_group();group.add_argument('--plan',action='store_true');group.add_argument('--apply-names',action='store_true');group.add_argument('--drop-retired-columns',action='store_true')
    parser.add_argument('--deployed-revision')
    args=parser.parse_args()
    if args.drop_retired_columns and not args.deployed_revision:parser.error('Verify compatible API/jobs deployment and provide --deployed-revision before dropping columns')
    try:receipt=run(args)
    except Exception as error:
        print(json.dumps({'result':'FAILED','category':type(error).__name__}));return 1
    args.receipt.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({key:value for key,value in receipt.items() if key!='updates'}))
    return 0


if __name__=='__main__':raise SystemExit(main())
