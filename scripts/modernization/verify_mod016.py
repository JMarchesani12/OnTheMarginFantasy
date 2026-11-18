"""MOD-016 preview/history/atomic maintenance on owned marked loopback PostgreSQL."""
import datetime as dt
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from assess_postgres import LOCAL,ROOT,engine_for
from verify_mod015 import SEED
from verify_mod014 import StrictOwner,tests as prior_finalization_tests
from verify_mod013 import tests as prior_weekly_tests
from verify_schedule_calendar import tests as prior_calendar_tests
from verify_scoring_complete import remaining_tests as prior_scoring_tests
from verify_mod010 import race
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.schedule.maintenance_service import CalendarMaintenanceService
from endpoints.scoring.service import ScoringService
from endpoints.scoring.weekly_service import WeeklyCompletionService
from endpoints.scoring.finalization_service import SeasonFinalizationService
from endpoints.transaction.workflow_service import TransactionWorkflowService
from endpoints.draft.pick_service import DraftPickService
from endpoints.draft.control_service import DraftControlService

NOW=dt.datetime(2026,11,6,12,tzinfo=dt.timezone.utc)


def tests(engine,database):
    def query(statement,**params):
        with engine.begin() as conn:
            result=conn.execute(text(statement),params) if params else conn.exec_driver_sql(statement)
            return [dict(r) for r in result.mappings()] if result.returns_rows else []
    def reset():
        with engine.begin() as conn:
            conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth; CREATE TABLE auth.users(id uuid PRIMARY KEY); CREATE EXTENSION pg_trgm WITH SCHEMA public;')
            conn.exec_driver_sql((ROOT/'db/baselines/20261029/001_schema.sql').read_text())
            conn.exec_driver_sql((ROOT/'api/migrations/20261030_game_kickoff_tbd.sql').read_text())
        for filename in ('20261104_user_identity_unique.sql','20261104_week_score_identity.sql','20261104_ownership_integrity.sql'):
            raw=engine.raw_connection()
            try:
                with raw.cursor() as cur:cur.execute((ROOT/'api/migrations'/filename).read_text())
                raw.commit()
            finally:raw.close()
        query(SEED)
        query('''DELETE FROM "WeeklyTeamScore"; DELETE FROM "LeagueTeamSlot";
            UPDATE "League" SET status='Pre-Draft'; UPDATE "Week" SET "isLocked"=false,"scoringComplete"=false;
            UPDATE "SportSeason" SET "seasonStart"='2026-10-05',"seasonEnd"='2026-10-25';
            INSERT INTO "SportSeasonSubdivision" ("sportSeasonId",code,name,"regularSeasonStart","regularSeasonEnd") VALUES (1,'D1','Synthetic','2026-10-05','2026-10-25'),(2,'FBS','Synthetic','2026-10-05','2026-10-25');''')
    def service(owner=engine):
        strict=StrictOwner(owner);schedule=ScheduleReadService(strict)
        return CalendarMaintenanceService(strict,schedule,ScoringService(strict,schedule))
    def state():
        return {t:query(f'SELECT * FROM "{t}" ORDER BY 1') for t in ('Week','WeeklyTeamScore','LeagueTeamSlot','Transaction','DraftPick','DraftState','DraftTurn','SportSeason','League')}
    def preview(owner=engine):return service(owner).run(2026,[10],now=NOW)
    def apply(owner=engine):return service(owner).run(2026,[10],apply=True,now=NOW)
    def scoped(current):
        return {t:[r for r in rows if r.get('leagueId',r.get('id'))==10] for t,rows in current.items() if t not in ('League','SportSeason')}
    reset();before=state();result=preview()
    assert not result['failures'],result
    assert result['leagues'][0]['outcome']=='preview' and result['leagues'][0]['plan']['eligible'],result
    assert state()==before,'Preview wrote data'
    result=apply();assert result['leagues'][0]['outcome']=='applied' and not result['failures'],result
    ids=result['leagues'][0]['weekIds'];assert ids[:2]==[100,101] and len(ids)==3,ids
    assert len(query('SELECT * FROM "WeeklyTeamScore" WHERE "leagueId"=10'))==6
    after=state();assert apply()['leagues'][0]['outcome']=='blocked';assert state()==after

    reset();football=service().run(2026,[30],apply=True,now=NOW)
    assert football['leagues'][0]['outcome']=='applied' and not football['failures'],football
    football_weeks=query('SELECT id,"weekNumber" FROM "Week" WHERE "leagueId"=30 ORDER BY "weekNumber"')
    assert football_weeks[0]['weekNumber']==0 and next(r['id'] for r in football_weeks if r['weekNumber']==1)==300
    assert len(query('SELECT id FROM "WeeklyTeamScore" WHERE "leagueId"=30'))==len(football_weeks)
    # Historical postseason merge would remove week3, cascade its transaction,
    # and change ownership endpoints. No mapping/rewrite is attempted.
    reset();query('''INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate","isLocked","scoringComplete") VALUES (103,10,3,'2026-10-19','2026-10-25',true,true);
        INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","droppedWeek","acquiredVia") VALUES (10,11,101,1,3,'Draft'),(10,11,102,3,NULL,'Trade'),(10,12,102,1,3,'Draft'),(10,12,101,3,NULL,'Trade');
        INSERT INTO "Transaction" (id,"leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds") VALUES (1,10,103,'TRADE',11,12,'COMPLETED','[101]','[102]');
        INSERT INTO "WeeklyTeamScore" ("leagueId","weekId","memberId","pointsAwarded","pointDifferential",rank) VALUES (10,100,11,7,10,1),(10,103,12,3,-10,2);
        INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name,rules,"startDate","endDate") VALUES (30,1,'PrimaryPlayoffs','Merged final','{"scoringPeriod":"BASKETBALL_FINAL"}','2026-10-12','2026-10-26');''')
    before=state();plan=preview()['leagues'][0]['plan']
    assert not plan['eligible'] and any(p['change']=='removed' and p['weekId']==103 for p in plan['periods']),plan
    assert plan['transactions'][0]['impact']=='period_removed'
    assert plan['scoreTotals']==[{'memberId':11,'pointsAwarded':7},{'memberId':12,'pointsAwarded':3}]
    assert apply()['leagues'][0]['outcome']=='blocked';assert state()==before,'Historical meanings/totals changed'
    historical={'scoreTotals':plan['scoreTotals'],'transactionImpact':plan['transactions'][0]['impact'],
                'ownershipImpacts':plan['ownership'],'removedWeekIds':[p['weekId'] for p in plan['periods'] if p['change']=='removed']}
    # A malformed foreign league transaction reference also prevents deletion.
    reset();query('''INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate","isLocked") VALUES (99,10,9,'2027-01-01','2027-01-07',false);
        INSERT INTO "Transaction" ("leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds") VALUES (20,99,'FREE_AGENT',21,21,'COMPLETED','[]','[]');''')
    before=state();result=apply();assert 'transaction_history' in result['leagues'][0]['plan']['reasons'];assert state()==before

    faults=[]
    for marker in ('SET "startDate"','INSERT INTO "Week"','DELETE FROM "Week"','INSERT INTO "WeeklyTeamScore"','SET "scoringComplete"'):
        reset();query('''INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate","isLocked") VALUES (99,10,9,'2027-01-01','2027-01-07',false);''')
        before=state();hit=False
        def fail(conn,cursor,statement,params,context,many):
            nonlocal hit
            if marker in statement and not hit:hit=True;raise RuntimeError('synthetic private SQL')
        event.listen(engine,'after_cursor_execute',fail)
        try:result=service().run(2026,[10,20],apply=True,now=NOW)
        finally:event.remove(engine,'after_cursor_execute',fail)
        assert hit and result['failures']==[{'leagueId':10,'stage':'apply','category':'RuntimeError'}],result
        assert result['leagues'][0]['leagueId']==20 and result['leagues'][0]['outcome']=='applied',result
        assert scoped(state())==scoped(before),(marker,scoped(state()),scoped(before))
        assert apply()['leagues'][0]['outcome']=='applied'
        faults.append(marker)
    for table in ('Week','WeeklyTeamScore'):
        reset();before=state()
        query(f'''CREATE FUNCTION reject_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
            IF NEW."leagueId"=10 THEN RAISE EXCEPTION 'synthetic deferred failure' USING ERRCODE='23514'; END IF;
            RETURN NEW; END $$;
            CREATE CONSTRAINT TRIGGER reject_commit AFTER INSERT OR UPDATE ON "{table}" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_commit();''')
        result=apply();assert result['failures'] and not result['leagues'],result
        assert state()==before,'Deferred commit did not restore whole league'
        query(f'DROP TRIGGER reject_commit ON "{table}"');assert apply()['leagues'][0]['outcome']=='applied'
    # Exact explicit scope and aggregate history guards on actual schema.
    reset();result=service().run(2026,[10,40,999],now=NOW)
    assert result['scopeErrors']==[{'leagueId':40,'reason':'wrong_season'},{'leagueId':999,'reason':'not_found'}]
    for edit,reason in (("UPDATE \"League\" SET status='In-Season' WHERE id=10",'league_not_unused'),
                        ('UPDATE "SportSeason" SET "seasonFinalized"=true WHERE id=1','season_finalized'),
                        ('UPDATE "Week" SET "isLocked"=true WHERE id=100','period_history')):
        reset();query(edit);before=state();result=apply();assert reason in result['leagues'][0]['plan']['reasons'];assert state()==before

    reports={};races={}
    def maintain(owner):
        reports['maintenance']=apply(owner)
        assert not reports['maintenance']['failures'],reports['maintenance']
    def weekly(owner):
        strict=StrictOwner(owner);schedule=ScheduleReadService(strict)
        reports['weekly']=WeeklyCompletionService(strict,ScoringService(strict,schedule),TransactionWorkflowService(strict)).run(NOW)
        assert not reports['weekly']['failures'],reports['weekly']
    reset();query('INSERT INTO "DraftState" ("leagueId",status) VALUES (10,\'pre\')')
    query('''UPDATE "League" SET settings=settings || '{"draft":{"draftType":"SNAKE","selectionTime":60,"numberOfRounds":2,"timeoutAction":"AUTO-SKIP","graceSeconds":0}}'::jsonb WHERE id=10''')
    def start(owner):reports['start']=DraftControlService(owner).start_for_job(10)
    races['draft_start_then_maintenance']=race(engine,database,start,maintain,'FROM "DraftState"',expected_second='ok')
    assert reports['maintenance']['leagues'][0]['outcome']=='blocked'
    # No-state path must not acquire a newly appeared state lock under League.
    reset();query('''UPDATE "League" SET settings=settings || '{"draft":{"draftType":"SNAKE","selectionTime":60,"numberOfRounds":2,"timeoutAction":"AUTO-SKIP","graceSeconds":0}}'::jsonb WHERE id=10''')
    races['first_start_then_maintenance']=race(engine,database,start,maintain,'INSERT INTO "DraftState"',expected_second='ok')
    assert 'draft_state_changed' in reports['maintenance']['leagues'][0]['plan']['reasons']
    # Order configuration remains legal history-free activity; use the same row
    # lock order and preserve its committed order while maintenance proceeds.
    reset();query('INSERT INTO "DraftState" ("leagueId",status) VALUES (10,\'pre\')')
    races['draft_order_then_maintenance']=race(engine,database,
        lambda owner:DraftControlService(owner).set_order_for_job(10,[12,11]),maintain,'FROM "DraftState"',expected_second='ok')
    assert reports['maintenance']['leagues'][0]['outcome']=='applied'
    assert [r['id'] for r in query('SELECT id FROM "LeagueMember" WHERE "leagueId"=10 ORDER BY "draftOrder"')]==[12,11]
    reset();query('INSERT INTO "DraftState" ("leagueId",status,"currentMemberId") VALUES (10,\'pre\',11)')
    before=state();assert 'draft_not_unused' in apply()['leagues'][0]['plan']['reasons'];assert state()==before
    reset();before=state()
    races['weekly_then_maintenance']=race(engine,database,weekly,maintain,'INSERT INTO "WeeklyTeamScore"',expected_second='ok')
    assert reports['maintenance']['leagues'][0]['outcome']=='blocked'
    assert [(r['id'],r['startDate'],r['endDate']) for r in state()['Week']]==[(r['id'],r['startDate'],r['endDate']) for r in before['Week']]
    reset()
    races['draft_then_maintenance']=race(engine,database,
        lambda owner:DraftPickService(owner).allocate_manual_for_job(10,11,103),maintain,'INSERT INTO "LeagueTeamSlot"',expected_second='ok')
    assert reports['maintenance']['leagues'][0]['outcome']=='blocked'
    reset()
    races['pending_then_maintenance']=race(engine,database,
        lambda owner:TransactionWorkflowService(owner).free_agency_for_job(10,100,1,11,103,None),maintain,'INSERT INTO "Transaction"',expected_second='ok')
    assert reports['maintenance']['leagues'][0]['outcome']=='blocked'
    reset()
    races['maintenance_then_weekly']=race(engine,database,maintain,weekly,'SET "startDate"',expected_second='ok')
    assert reports['maintenance']['leagues'][0]['outcome']=='applied'
    week_ids=reports['maintenance']['leagues'][0]['weekIds']
    assert not set(week_ids)&set(reports['weekly']['closed'])
    assert len(query('SELECT * FROM "WeeklyTeamScore" WHERE "leagueId"=10'))==6
    reset();query('''INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate","isLocked") VALUES (99,10,9,'2027-01-01','2027-01-07',false);''')
    def foreign_reference(owner):
        with owner.begin() as conn:conn.exec_driver_sql('''INSERT INTO "Transaction" ("leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds") VALUES (20,99,'FREE_AGENT',21,21,'COMPLETED','[]','[]')''')
    races['foreign_reference_then_maintenance']=race(engine,database,foreign_reference,maintain,'INSERT INTO "Transaction"',expected_second='ok')
    assert reports['maintenance']['leagues'][0]['outcome']=='blocked' and query('SELECT id FROM "Week" WHERE id=99')
    reset();score=ScoringService(engine,ScheduleReadService(engine))
    for row in query('SELECT "leagueId","weekNumber" FROM "Week" WHERE "leagueId" IN (10,20)'):
        score.compute_weekly_scores_for_job(row['leagueId'],row['weekNumber'])
    query('UPDATE "Week" SET "scoringComplete"=true,"isLocked"=true WHERE "leagueId" IN (10,20)')
    def finalize(owner):
        strict=StrictOwner(owner);reports['finalize']=SeasonFinalizationService(strict,ScoringService(strict,ScheduleReadService(strict))).run(NOW)
        assert 1 in reports['finalize']['finalized'],reports['finalize']
    races['finalization_then_maintenance']=race(engine,database,finalize,maintain,'FROM "SportSeason" WHERE id=',expected_second='ok')
    assert 'season_finalized' in reports['maintenance']['leagues'][0]['plan']['reasons']
    return {'preview_invariance_exact_scope':'PASS','historical_postseason_refusal':historical,
            'football_week_zero_same_transaction':'PASS','foreign_reference_cascade_refusal':'PASS','unused_repair_ids_real_scoring_retry':'PASS',
            'statement_faults':faults,'whole_league_deferred_commit_restore':'PASS','races':races}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_mod016_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'mod016-owner');result=tests(engine,name)
        result['prior_calendar']=prior_calendar_tests(engine)
        result['prior_weekly']=prior_weekly_tests(engine,name)
        result['prior_finalization']=prior_finalization_tests(engine,name)
        result['prior_scoring']=prior_scoring_tests(engine,name)
        files=['api/endpoints/schedule/'+file for file in ('maintenance_repository.py','maintenance_service.py','calendar_service.py','calendar_repository.py','read_service.py','read_repository.py')]
        files+=['api/scripts/rebuild_weeks_and_rescore.py','api/endpoints/scoring/service.py','api/endpoints/scoring/repository.py','api/endpoints/scoring/weekly_service.py','api/endpoints/scoring/finalization_service.py','api/utils/ownership.py',
                'api/tests/test_calendar_maintenance.py','api/tests/test_calendar_maintenance_cli.py',
                'scripts/modernization/verify_mod016.py','scripts/modernization/verify_mod014.py','scripts/modernization/verify_mod013.py','scripts/modernization/verify_mod015.py','scripts/modernization/verify_schedule_calendar.py','scripts/modernization/verify_scoring_complete.py',
                'api/migrations/20261030_game_kickoff_tbd.sql','api/migrations/20261104_user_identity_unique.sql','api/migrations/20261104_week_score_identity.sql','api/migrations/20261104_ownership_integrity.sql','db/baselines/20261029/001_schema.sql']
        report={'result':'PASS','scope':'Owned marked loopback PostgreSQL only; no configured maintenance/job/history writes','tests':result,
                'sha256':{file:hashlib.sha256((ROOT/file).read_bytes()).hexdigest() for file in files}}
        (ROOT/'docs/modernization/evidence/mod-016-postgres-2026-11-06.json').write_text(json.dumps(report,indent=2,default=str)+'\n');print(json.dumps(report,indent=2,default=str))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()
if __name__=='__main__':main()
