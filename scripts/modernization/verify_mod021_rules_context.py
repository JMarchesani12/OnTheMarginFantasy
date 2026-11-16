"""Rules-only scoring equivalence/recovery on a marked disposable local database."""
from datetime import datetime,timedelta,timezone
import hashlib
from pathlib import Path
import subprocess
import types
from uuid import uuid4
from unittest.mock import patch
import psycopg2
from sqlalchemy import create_engine,event,text
from sqlalchemy.exc import DBAPIError
import measure_mod017 as base
import measure_mod021_weekly as fixture
from measure_mod017_transactions import save_json,verify_cleanup
from endpoints.scoring.service import ScoringService
from endpoints.schedule.read_service import ScheduleReadService
import rules.leagueRules as definitions


def snapshot(conn):
    return [dict(r) for r in conn.exec_driver_sql('SELECT * FROM "WeeklyTeamScore" ORDER BY "leagueId","weekId","memberId"').mappings()]


def stored(conn,league=101,week=2000):
    return [dict(r) for r in conn.execute(text('SELECT "memberId","pointDifferential",rank,"pointsAwarded" FROM "WeeklyTeamScore" WHERE "leagueId"=:league AND "weekId"=:week ORDER BY rank'),dict(league=league,week=week)).mappings()]


def seed_old_scores(conn):
    conn.exec_driver_sql('DELETE FROM "WeeklyTeamScore" WHERE "leagueId"=101')
    conn.execute(text('INSERT INTO "WeeklyTeamScore" ("leagueId","weekId","memberId","pointDifferential",rank,"pointsAwarded") VALUES (101,2000,1001,999,1,4),(101,2000,1002,888,2,3)'))


def expected(order,diffs,offset=1000):
    return [dict(memberId=offset+m,teamName=f'Audit team {m}',pointDifferential=diffs[m-1],rank=i,pointsAwarded=len(order)-i+1) for i,m in enumerate(order,1)]


def semantic_cases(engine,anchor,Legacy):
    records=[];clock=datetime.fromisoformat(anchor)
    for name in ('mixed_ties','ownership_transfer','week_zero','unranked','final_zero','final_split','final_future','cross_league'):
        with engine.connect() as conn:fixture.seed_scenario(conn,4,'unique',anchor)
        with engine.connect() as conn:
            tx=conn.begin()
            try:
                league=101;number=1;week=2000;want=None;reject=False;current=ScoringService(None,ScheduleReadService(None))
                if name=='mixed_ties':
                    for i,margin in enumerate([5,5,1,1],1):conn.execute(text('UPDATE "GameResult" SET "homeScore"=100+CASE WHEN "homeTeamId"=32 THEN -:margin ELSE :margin END WHERE id=:id'),dict(margin=margin,id=i))
                    want=expected([1,2,3,4],[5,5,1,1])
                elif name=='ownership_transfer':
                    conn.execute(text('UPDATE "LeagueTeamSlot" SET "droppedWeek"=2 WHERE "leagueId"=101 AND "sportTeamId"=1'))
                    conn.exec_driver_sql('INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") VALUES (101,1002,1,2,\'TRADE\')')
                    conn.execute(text('INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate") VALUES (2001,101,2,:s,:e)'),dict(s=clock-timedelta(days=6),e=clock-timedelta(days=1)))
                    # Week1 must retain the original owner at the exclusive drop boundary.
                    old=current.compute_weekly_scores_for_job(101,1,conn=conn)
                    assert old['scores']==fixture.expected_scores(4,'unique')
                    conn.execute(text('UPDATE "GameResult" SET date=:date'),dict(date=clock-timedelta(days=3)))
                    number=2;week=2001;want=expected([2,3,4,1],[-29,36,2,1])
                elif name=='week_zero':
                    conn.execute(text('INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate") SELECT 2002,"leagueId",0,"startDate","endDate" FROM "Week" WHERE id=2000'))
                    conn.exec_driver_sql('UPDATE "LeagueTeamSlot" SET "acquiredWeek"=0 WHERE "leagueId"=101')
                    number=0;week=2002;want=fixture.expected_scores(4,'unique')
                elif name=='unranked':
                    conn.exec_driver_sql('UPDATE "GameResult" SET "homeTeamId"=CASE WHEN "homeTeamId"=32 THEN NULL ELSE "homeTeamId" END, "awayTeamId"=CASE WHEN "awayTeamId"=32 THEN NULL ELSE "awayTeamId" END')
                    want=expected([1,2,3,4],[2,2,1,1])
                elif name.startswith('final_'):
                    if name=='final_zero':conn.exec_driver_sql('DELETE FROM "GameResult"');want=expected([1,2,3,4],[0,0,0,0])
                    start=clock-timedelta(days=14);end=clock-timedelta(days=7)+timedelta(microseconds=1)
                    if name=='final_split':start-=timedelta(days=1);reject=True
                    if name=='final_future':
                        start=clock+timedelta(days=1);end=clock+timedelta(days=8);reject=True
                        conn.execute(text('UPDATE "Week" SET "startDate"=:s,"endDate"=:e WHERE id=2000'),dict(s=start,e=end-timedelta(microseconds=1)))
                    conn.execute(text('INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name,"startDate","endDate",rules) VALUES (99,2026,\'NationalTournament\',\'Final\',:s,:e,jsonb_build_object(\'scoringPeriod\',\'BASKETBALL_FINAL\'))'),dict(s=start,e=end))
                elif name=='cross_league':
                    conn.exec_driver_sql('''INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear") SELECT 102,'Second',sport,4,status,settings,commissioner,"seasonYear" FROM "League" WHERE id=101;
                    INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") SELECT id+1000,102,"userId","teamName","draftOrder" FROM "LeagueMember" WHERE "leagueId"=101;
                    INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate") SELECT 3000,102,1,"startDate","endDate" FROM "Week" WHERE id=2000;
                    INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") SELECT 102,"memberId"+1000,"sportTeamId",1,'DRAFT' FROM "LeagueTeamSlot" WHERE "leagueId"=101''')
                    first=current.compute_weekly_scores_for_job(101,1,conn=conn)
                    assert first['scores']==fixture.expected_scores(4,'unique');league=102;week=3000
                    want=expected([1,2,3,4],[4,3,2,1],offset=2000)
                seed_old_scores(conn);before=snapshot(conn);outputs=[]
                for Scorer in (ScoringService,Legacy):
                    nested=conn.begin_nested()
                    try:
                        try:result=(current if Scorer is ScoringService else Scorer(None,ScheduleReadService(None))).compute_weekly_scores_for_job(league,number,conn=conn)
                        except ValueError:
                            if not reject:raise
                            assert snapshot(conn)==before;outputs.append(dict(rejected=True));continue
                        assert not reject;assert result['scores']==want,(name,result['scores'],want)
                        target=stored(conn,league,week)
                        assert target==[{k:r[k] for k in ('memberId','pointDifferential','rank','pointsAwarded')} for r in want]
                        outputs.append(dict(result=result,stored=target))
                    finally:nested.rollback()
                assert outputs[0]==outputs[1];assert snapshot(conn)==before
                records.append(dict(case=name,reference_equivalent=True,logical_scores=base.signature(want or []),rejected=reject,existing_scores_rollback=True))
            finally:tx.rollback()
    return records


def replacement_checks(engine,anchor):
    records=[]
    for fail in ('delete','insert1','insert2','insert3','insert4','commit','rules','caller'):
        with engine.connect() as conn:fixture.seed_scenario(conn,4,'unique',anchor)
        with engine.begin() as conn:seed_old_scores(conn)
        with engine.connect() as conn:before=snapshot(conn)
        seen=[]
        def inject(conn,cursor,statement,params,context,many):
            if statement.lstrip().startswith('DELETE FROM "WeeklyTeamScore"') and fail=='delete':raise RuntimeError('after delete')
            if statement.lstrip().startswith('INSERT INTO "WeeklyTeamScore"'):
                seen.append(1)
                if fail=='insert'+str(len(seen)):raise RuntimeError('after insert')
        schedule=ScheduleReadService(None)
        if fail=='rules':schedule.resolve_member_game_rules_for_scoring=lambda *a:(_ for _ in ()).throw(ValueError('synthetic rules failure'))
        if fail=='commit':
            with engine.begin() as conn:conn.exec_driver_sql('''CREATE FUNCTION mod021_fail_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic commit'; END $$;
            CREATE CONSTRAINT TRIGGER mod021_commit AFTER INSERT ON "WeeklyTeamScore" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mod021_fail_commit();''')
        event.listen(engine,'after_cursor_execute',inject)
        try:
            try:
                with engine.begin() as conn:
                    ScoringService(None,schedule).compute_weekly_scores_for_job(101,1,conn=conn)
                    if fail=='caller':raise RuntimeError('caller rollback')
            except (ValueError,RuntimeError,DBAPIError):pass
            else:raise AssertionError('Expected injected failure missing')
        finally:
            event.remove(engine,'after_cursor_execute',inject)
            if fail=='commit':
                with engine.begin() as conn:conn.exec_driver_sql('DROP TRIGGER mod021_commit ON "WeeklyTeamScore"; DROP FUNCTION mod021_fail_commit()')
        with engine.connect() as conn:assert snapshot(conn)==before
        with engine.begin() as conn:
            result=ScoringService(None,ScheduleReadService(None)).compute_weekly_scores_for_job(101,1,conn=conn)
            assert result['scores']==fixture.expected_scores(4,'unique')
        with engine.connect() as conn:assert stored(conn)==[{k:r[k] for k in ('memberId','pointDifferential','rank','pointsAwarded')} for r in result['scores']]
        records.append(dict(failure=fail,prior_rows_preserved=True,durable_retry=True))
    return records


def mutable_boundary(engine,anchor):
    records=[]
    # Only v1 exists in production. Add, never edit, a synthetic in-process
    # definition to exercise future-version boundary without publishing one.
    second={**dict(definitions.VERSIONS['v1']),'thresholds':{1:1,'default':1}}
    with patch.object(definitions,'VERSIONS',{**dict(definitions.VERSIONS),'audit-v2':second}):
        for kind in ('rules','tier','phase'):
            with engine.begin() as conn:conn.exec_driver_sql('UPDATE "League" SET settings=jsonb_build_object(\'ruleSetVersion\',\'v1\') WHERE id=101')
            with engine.connect() as conn:fixture.seed_scenario(conn,4,'tier_phase' if kind=='phase' else 'unique',anchor)
            if kind=='rules':
                with engine.begin() as conn:conn.exec_driver_sql('UPDATE "SportTeam" SET tier=2 WHERE id=32')
            mutated=[]
            def change():
                with engine.begin() as other:
                    if kind=='rules':other.exec_driver_sql('UPDATE "League" SET settings=jsonb_build_object(\'ruleSetVersion\',\'audit-v2\') WHERE id=101')
                    elif kind=='tier':other.exec_driver_sql('UPDATE "SportTeam" SET tier=3 WHERE id=32')
                    else:other.exec_driver_sql('UPDATE "SeasonPhase" SET rules=jsonb_build_object(\'positiveOnly\',true,\'marginMultiplier\',2) WHERE id=1')
                mutated.append(True)
            class Schedule(ScheduleReadService):
                def get_member_games_for_week(self,*a,**kw):
                    result=super().get_member_games_for_week(*a,**kw)
                    if kind!='rules' and not mutated:change() # precise after-first-member barrier
                    return result
            class Scorer(ScoringService):
                def _create_weekly_rules_context(self,*a):
                    context=super()._create_weekly_rules_context(*a)
                    if kind=='rules' and not mutated:change() # precise after-context barrier
                    return context
            scorer=Scorer(None,Schedule(None))
            with engine.connect() as conn:
                tx=conn.begin()
                try:
                    first=scorer.compute_weekly_scores_for_job(101,1,conn=conn)
                    want=([4,3,2,1] if kind=='rules' else [4,2,1,1] if kind=='tier' else [12,12,8,4])
                    assert first['scores']==expected([1,2,3,4],want),(kind,first['scores'])
                    second_result=scorer.compute_weekly_scores_for_job(101,1,conn=conn)
                    want_second=([2,2,1,1] if kind=='rules' else [2,2,1,1] if kind=='tier' else [16,12,8,4])
                    assert second_result['scores']==expected([1,2,3,4],want_second),(kind,second_result['scores'])
                    records.append(dict(kind=kind,mutation_on_second_connection=True,barrier='after context' if kind=='rules' else 'after first member',first=first['scores'],second=second_result['scores'],scope='rules fixed per call, tiers/phases retain statement visibility; synthetic audit-v2 registry only'))
                finally:tx.rollback()
    return records


def run():
    directory=base.ROOT/'docs/modernization/evidence';run_id=uuid4().hex;artifact=directory/f'mod-021-rules-context-{run_id}.json';manifest=directory/'mod-021-rules-context-current-2026-11-16.json'
    report=dict(run_id=run_id,result='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),provenance={},databases=[],cleanup='no database created')
    def persist():save_json(artifact,report);save_json(manifest,dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=base.ROOT,text=True).strip()
        source=subprocess.check_output(['git','show',revision+':api/endpoints/scoring/service.py'],cwd=base.ROOT)
        assert b'_WeeklyRulesContext' not in source,'Reference must precede context implementation'
        module=types.ModuleType('endpoints.scoring._historical_reference');module.__package__='endpoints.scoring';exec(compile(source,'historical-scoring-service','exec'),module.__dict__)
        report['historical_reference']=dict(revision=revision,path='api/endpoints/scoring/service.py',sha256=hashlib.sha256(source).hexdigest())
        files=[base.BASELINE,*base.MIGRATIONS,fixture.TBD,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod021_weekly.py','scripts/modernization/verify_mod021_rules_context.py','api/endpoints/scoring/service.py','api/endpoints/scoring/weekly_context.py','api/endpoints/scoring/repository.py','api/endpoints/schedule/read_service.py','api/endpoints/schedule/read_repository.py','api/endpoints/schedule/calendar_service.py','api/endpoints/schedule/calendar_repository.py','api/rules/leagueRules.py','api/rules/tournamentRules.py','api/utils/conference_membership.py']
        report['provenance']={f:hashlib.sha256((base.ROOT/f).read_bytes()).hexdigest() for f in files}
        admin=psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        try:
            with base.owned_database(admin) as name:
                record=dict(name=name,cleanup='pending');report['databases'].append(record);persist()
                engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
                try:
                    with engine.connect() as conn:base.schema(conn);facts=fixture.seed(conn,4)
                    report['fixture']=facts;report['semantics']=semantic_cases(engine,facts['anchor'],module.ScoringService);report['replacement']=replacement_checks(engine,facts['anchor']);report['mutable_boundary']=mutable_boundary(engine,facts['anchor'])
                finally:engine.dispose()
        finally:
            for record in report['databases']:verify_cleanup(admin,record)
            report['cleanup']='verified' if report['databases'] and all(r['cleanup']=='removed' for r in report['databases']) else 'unverified'
        assert report['cleanup']=='verified';report['result']='PASS';return report
    except BaseException as error:report['result']='FAILED';report['error']=str(error);report['error_type']=type(error).__name__;raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();persist()
        if admin is not None:admin.close()
        print(artifact.name,report['result'],report['cleanup'],flush=True)
if __name__=='__main__':run()
