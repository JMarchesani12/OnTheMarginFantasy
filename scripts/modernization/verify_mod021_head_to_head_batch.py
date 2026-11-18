"""Per-group raw H2H parity and transaction checks; marked owned local DB only."""
from datetime import datetime,timedelta,timezone
from itertools import combinations
import hashlib,types,json
from uuid import uuid4
import psycopg2
from sqlalchemy import create_engine,event,text
from sqlalchemy.exc import DBAPIError
import measure_mod017 as base
import measure_mod021_weekly as fixture
import verify_mod021_rules_context as shared
from measure_mod017_transactions import save_json,verify_cleanup
from endpoints.scoring.service import ScoringService
from endpoints.schedule.read_service import ScheduleReadService

PRE_BATCH='49cd228ea9c05ab05894fdddeb42c25174d91f6c'
PRE_BATCH_HASH='5a32ad6a4e9c2eea5266e3828213368a5eb03acec0b9b10e415636cbeada282b'
IDS=[1001,1002,1003,1004]


def pair_rows(batch,a,b):
    rows=[]
    for row in batch:
        h=set(row['homeMemberIds']);w=set(row['awayMemberIds'])
        if (a in h and b in w) or (a in w and b in h):
            rows.append(dict(id=row['id'],homeScore=row['homeScore'],awayScore=row['awayScore'],homeOwnedByA=a in h,awayOwnedByA=a in w,homeOwnedByB=b in h,awayOwnedByB=b in w))
    return rows


def pair_parity(conn,ids=IDS,week=1):
    schedule=ScheduleReadService(None);batch=schedule.get_head_to_head_games_for_members(101,ids,week,conn)
    assert len(batch)==len({r['id'] for r in batch})
    union=set();checks=[]
    for a,b in combinations(ids,2):
        old=schedule.get_head_to_head_games(101,a,b,week,conn=conn)
        projected=[{k:r[k] for k in ('id','homeScore','awayScore','homeOwnedByA','awayOwnedByA','homeOwnedByB','awayOwnedByB')} for r in old]
        got=pair_rows(batch,a,b);assert got==projected,(a,b,got,projected)
        union.update(r['id'] for r in old);checks.append(dict(a=a,b=b,rows=len(got),fingerprint=base.signature(got)))
    assert union=={r['id'] for r in batch}
    return dict(batch_ids=[r['id'] for r in batch],pairs=checks)


def pair_cases(engine,anchor):
    records=[];clock=datetime.fromisoformat(anchor)
    for name in ('ordinary','no_cross','start','end','before','null_start','time_tbd','unmapped','foreign_season','foreign_sport','foreign_member','transfer','legacy_duplicates','invalid_ineligible','invalid_eligible'):
        with engine.connect() as conn:fixture.seed_scenario(conn,4,'unique' if name=='no_cross' else 'head_decides',anchor)
        with engine.connect() as conn:
            tx=conn.begin()
            try:
                cross='"homeTeamId"=1 AND "awayTeamId"=2'
                if name in ('start','end','before'):
                    value=clock-timedelta(days=14 if name in ('start','before') else 7)
                    if name=='before':value-=timedelta(microseconds=1)
                    conn.execute(text('UPDATE "GameResult" SET date=:date WHERE '+cross),dict(date=value))
                elif name=='null_start':conn.exec_driver_sql('UPDATE "Week" SET "startDate"=NULL WHERE id=2000')
                elif name=='time_tbd':conn.exec_driver_sql('UPDATE "GameResult" SET "timeTBD"=true WHERE '+cross)
                elif name=='unmapped':conn.exec_driver_sql('UPDATE "GameResult" SET "awayTeamId"=NULL WHERE '+cross)
                elif name=='foreign_season':
                    conn.exec_driver_sql('INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (2025,1,2025,\'2025-01-01\',\'2025-12-31\')')
                    conn.exec_driver_sql('UPDATE "GameResult" SET "sportSeasonId"=2025 WHERE '+cross)
                elif name=='foreign_sport':
                    conn.exec_driver_sql('INSERT INTO "Sport" (id,name,"maxPlayersToHaveMaxRounds","maxDraftRounds") VALUES (2,\'Other\',8,4)')
                    conn.exec_driver_sql('UPDATE "GameResult" SET sport=2 WHERE '+cross)
                elif name=='transfer':
                    conn.exec_driver_sql('UPDATE "LeagueTeamSlot" SET "droppedWeek"=2 WHERE "leagueId"=101 AND "sportTeamId"=1')
                    conn.exec_driver_sql('INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") VALUES (101,1003,1,2,\'TRADE\')')
                    before=pair_parity(conn);assert before['batch_ids']
                    conn.exec_driver_sql('UPDATE "Week" SET "weekNumber"=2 WHERE id=2000')
                elif name=='legacy_duplicates':
                    # Session-local legacy relation only; public constraints remain intact.
                    conn.exec_driver_sql('CREATE TEMP TABLE "LeagueTeamSlot" AS SELECT * FROM public."LeagueTeamSlot" WHERE "leagueId"=101')
                    conn.exec_driver_sql('INSERT INTO pg_temp."LeagueTeamSlot" SELECT * FROM pg_temp."LeagueTeamSlot"')
                    conn.exec_driver_sql('INSERT INTO pg_temp."LeagueTeamSlot" SELECT * FROM pg_temp."LeagueTeamSlot" WHERE "sportTeamId"=1 LIMIT 1')
                    conn.exec_driver_sql('UPDATE pg_temp."LeagueTeamSlot" SET "memberId"=1002 WHERE id=(SELECT min(id) FROM pg_temp."LeagueTeamSlot" WHERE "sportTeamId"=1) AND ctid=(SELECT ctid FROM pg_temp."LeagueTeamSlot" WHERE "sportTeamId"=1 ORDER BY ctid DESC LIMIT 1)')
                elif name.startswith('invalid_'):
                    conn.exec_driver_sql('CREATE TEMP TABLE "GameResult" AS SELECT * FROM public."GameResult"')
                    predicate=cross if name=='invalid_eligible' else '"homeTeamId"=1 AND "awayTeamId"=5'
                    conn.exec_driver_sql('UPDATE pg_temp."GameResult" SET "homeScore"=NULL WHERE '+predicate)
                result=pair_parity(conn,[1001,999999] if name=='foreign_member' else IDS,2 if name=='transfer' else 1)
                if name=='invalid_eligible':
                    try:ScoringService(None,ScheduleReadService(None))._tb_weekly_head_to_head(101,1,[dict(memberId=i) for i in IDS],conn=conn)
                    except TypeError:pass
                    else:raise AssertionError('Invalid eligible score silently accepted')
                if name in ('no_cross','before','null_start','unmapped','foreign_season','foreign_sport','foreign_member'):assert result['batch_ids']==[]
                records.append(dict(case=name,parity=result,legacy_temp_relation=name in ('legacy_duplicates','invalid_ineligible','invalid_eligible')))
            finally:tx.rollback()
    return records


def mixed_games(conn,anchor,partial=False):
    conn.exec_driver_sql('DELETE FROM "GameResult"')
    games=[(1,32,0),(2,32,12),(1,2,7),(3,32,4),(3,32,-5),(4,32,6),(4,32,-5),(3,1,2),(1,5,29)]
    if partial:games=[(1,32,3),(2,32,20),(2,32,-17),(3,32,24),(4,32,0),(1,3,7),(2,3,7),(1,5,29)]
    for i,(home,away,margin) in enumerate(games,1):
        conn.execute(text('''INSERT INTO "GameResult" (id,sport,"externalGameId",date,"homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","sportSeasonId","timeTBD") VALUES (:id,1,:external,:date,:home,:away,:hs,100,:home,:away,'Home','Away',2026,false)'''),dict(id=i,external='mixed-'+str(i),date=datetime.fromisoformat(anchor)-timedelta(days=10),home=home,away=away,hs=100+margin))


def scoring_cases(engine,anchor,Legacy):
    records=[]
    for partial in (False,True):
        with engine.connect() as conn:fixture.seed_scenario(conn,4,'unique',anchor)
        with engine.begin() as conn:mixed_games(conn,anchor,partial)
        want=shared.expected([1,2,3,4] if partial else [1,2,4,3],[10,10,10,0] if partial else [5,5,1,1])
        with engine.connect() as conn:
            tx=conn.begin()
            try:
                outputs=[]
                for Scorer in (ScoringService,Legacy):
                    nested=conn.begin_nested();tracker=fixture.Tracker()
                    event.listen(engine,'before_cursor_execute',tracker.before);event.listen(engine,'after_cursor_execute',tracker.after)
                    try:
                        tracker.enabled=Scorer is ScoringService
                        result=Scorer(None,ScheduleReadService(None)).compute_weekly_scores_for_job(101,1,conn=conn)
                        tracker.enabled=False;assert result['scores']==want
                        assert shared.stored(conn)==[{k:r[k] for k in ('memberId','pointDifferential','rank','pointsAwarded')} for r in want]
                        if Scorer is ScoringService:
                            assert tracker.counts['head_to_head_group']==(1 if partial else 2)
                            assert tracker.counts['member_games']==(4 if partial else 6)
                        outputs.append(result)
                    finally:tracker.enabled=False;event.remove(engine,'before_cursor_execute',tracker.before);event.remove(engine,'after_cursor_execute',tracker.after);nested.rollback()
                assert outputs[0]==outputs[1];records.append(dict(case='partial_subtie' if partial else 'h2h_then_fallback',scores=want,reference_equal=True,group_queries=1 if partial else 2))
            finally:tx.rollback()
    return records


def recovery(engine,anchor):
    records=[]
    for fail in ('group','delete','insert1','insert2','insert3','insert4','commit','caller'):
        with engine.connect() as conn:fixture.seed_scenario(conn,4,'head_decides',anchor)
        with engine.begin() as conn:shared.seed_old_scores(conn)
        with engine.connect() as conn:before=shared.snapshot(conn)
        seen=[];calls=[]
        class Schedule(ScheduleReadService):
            def get_head_to_head_games_for_members(self,*a,**kw):
                rows=super().get_head_to_head_games_for_members(*a,**kw);calls.append(1)
                if fail=='group' and len(calls)==1:raise RuntimeError('after group read')
                return rows
        scorer=ScoringService(None,Schedule(None))
        def inject(conn,cursor,statement,params,context,many):
            if statement.lstrip().startswith('DELETE FROM "WeeklyTeamScore"') and fail=='delete':raise RuntimeError('after delete')
            if statement.lstrip().startswith('INSERT INTO "WeeklyTeamScore"'):
                seen.append(1)
                if fail=='insert'+str(len(seen)):raise RuntimeError('after insert')
        if fail=='commit':
            with engine.begin() as conn:conn.exec_driver_sql('''CREATE FUNCTION mod021_h2h_commit() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic commit'; END $$;
            CREATE CONSTRAINT TRIGGER mod021_h2h_commit AFTER INSERT ON "WeeklyTeamScore" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION mod021_h2h_commit();''')
        event.listen(engine,'after_cursor_execute',inject)
        try:
            try:
                with engine.begin() as conn:
                    scorer.compute_weekly_scores_for_job(101,1,conn=conn)
                    if fail=='caller':raise RuntimeError('caller')
            except (RuntimeError,DBAPIError):pass
            else:raise AssertionError('Injected failure missing')
        finally:
            event.remove(engine,'after_cursor_execute',inject)
            if fail=='commit':
                with engine.begin() as conn:conn.exec_driver_sql('DROP TRIGGER mod021_h2h_commit ON "WeeklyTeamScore"; DROP FUNCTION mod021_h2h_commit()')
        with engine.connect() as conn:assert shared.snapshot(conn)==before
        with engine.begin() as conn:result=scorer.compute_weekly_scores_for_job(101,1,conn=conn);assert result['scores']==fixture.expected_scores(4,'head_decides')
        assert len(calls)==2;records.append(dict(failure=fail,old_rows_preserved=True,fresh_batch_on_durable_retry=True))
    return records


def correction_boundary(engine,anchor):
    with engine.connect() as conn:fixture.seed_scenario(conn,4,'unique',anchor)
    with engine.begin() as conn:mixed_games(conn,anchor)
    calls=[]
    class Schedule(ScheduleReadService):
        def get_head_to_head_games_for_members(self,*a,**kw):
            rows=super().get_head_to_head_games_for_members(*a,**kw);calls.append(kw['member_ids'])
            if len(calls)==1:
                with engine.begin() as other:
                    other.exec_driver_sql('UPDATE "GameResult" SET "homeScore"=93 WHERE "homeTeamId"=1 AND "awayTeamId"=2')
                    other.execute(text('''INSERT INTO "GameResult" (id,sport,"externalGameId",date,"homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","sportSeasonId","timeTBD") VALUES (100,1,'correction',:date,3,4,109,100,3,4,'Home','Away',2026,false)'''),dict(date=datetime.fromisoformat(anchor)-timedelta(days=10)))
            return rows
    scorer=ScoringService(None,Schedule(None))
    with engine.connect() as conn:
        tx=conn.begin()
        try:
            first=scorer.compute_weekly_scores_for_job(101,1,conn=conn)
            assert first['scores']==shared.expected([1,2,3,4],[5,5,1,1]);assert calls==[[1001,1002],[1003,1004]]
            second=scorer.compute_weekly_scores_for_job(101,1,conn=conn)
            assert second['scores']==shared.expected([2,3,4,1],[-9,19,10,-8]);assert len(calls)==2
            return dict(first=first['scores'],second=second['scores'],groups=calls,barrier='after first group fetch; separate committed game correction',scope='Per-group statement only, not full-call snapshot')
        finally:tx.rollback()


def run():
    directory=base.ROOT/'docs/modernization/evidence';run_id=uuid4().hex;artifact=directory/f'mod-021-h2h-batch-{run_id}.json';manifest=directory/'mod-021-h2h-batch-current-2026-11-16.json'
    report=dict(run_id=run_id,result='RUNNING',started_at=datetime.now(timezone.utc).isoformat(),provenance={},databases=[],cleanup='no database created')
    def persist():save_json(artifact,report);save_json(manifest,dict(run_id=run_id,result=report['result'],artifact=artifact.name,cleanup=report['cleanup']))
    persist();admin=None
    try:
        source=shared.load_reference_source(PRE_BATCH,PRE_BATCH_HASH);module=types.ModuleType('endpoints.scoring._pre_batch');module.__package__='endpoints.scoring';exec(compile(source,'pre-batch-scorer','exec'),module.__dict__)
        report['reference']=dict(revision=PRE_BATCH,sha256=PRE_BATCH_HASH)
        old_path=directory/'mod-021-weekly-8f762d91a58f430da9319020b6919712.json'
        current_manifest=json.loads((directory/'mod-021-weekly-h2h-current-2026-11-16.json').read_text())
        new_path=directory/current_manifest['artifact']
        old=json.loads(old_path.read_text());new=json.loads(new_path.read_text())
        assert old['result']==new['result']=='PASS'
        old_cases={(tier['members'],case['scenario']):case['result'] for tier in old['tiers'] for case in tier['measurements']}
        new_cases={(tier['members'],case['scenario']):case['result'] for tier in new['tiers'] for case in tier['measurements']}
        assert len(old_cases)==15 and old_cases==new_cases
        report['count_score_equivalence']=dict(cases=15,previous=old_path.name,current=new_path.name,previous_sha256=hashlib.sha256(old_path.read_bytes()).hexdigest(),current_sha256=hashlib.sha256(new_path.read_bytes()).hexdigest(),scope='Full saved logical score signatures against frozen v2 actual-run evidence; two mixed cases also execute pinned scorer below')
        files=[base.BASELINE,*base.MIGRATIONS,fixture.TBD,'scripts/modernization/measure_mod017.py','scripts/modernization/measure_mod017_transactions.py','scripts/modernization/measure_mod021_weekly.py','scripts/modernization/verify_mod021_rules_context.py','scripts/modernization/verify_mod021_head_to_head_batch.py','api/endpoints/scoring/service.py','api/endpoints/scoring/weekly_context.py','api/endpoints/scoring/repository.py','api/endpoints/schedule/read_service.py','api/endpoints/schedule/read_repository.py','api/endpoints/schedule/calendar_service.py','api/endpoints/schedule/calendar_repository.py','api/rules/leagueRules.py','api/rules/tournamentRules.py']
        report['provenance']={f:hashlib.sha256((base.ROOT/f).read_bytes()).hexdigest() for f in files}
        admin=psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        try:
            with base.owned_database(admin) as name:
                record=dict(name=name,cleanup='pending');report['databases'].append(record);persist()
                engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
                try:
                    with engine.connect() as conn:base.schema(conn);facts=fixture.seed(conn,4)
                    report['fixture']=facts;report['pairs']=pair_cases(engine,facts['anchor']);report['scoring']=scoring_cases(engine,facts['anchor'],module.ScoringService);report['recovery']=recovery(engine,facts['anchor']);report['correction']=correction_boundary(engine,facts['anchor'])
                finally:engine.dispose()
        finally:
            for record in report['databases']:verify_cleanup(admin,record)
            report['cleanup']='verified' if report['databases'] and all(r['cleanup']=='removed' for r in report['databases']) else 'unverified'
        assert report['cleanup']=='verified';report['result']='PASS';return report
    except BaseException as error:report['result']='FAILED';report['error_type']=type(error).__name__;report['error']=str(error);raise
    finally:
        report['finished_at']=datetime.now(timezone.utc).isoformat();persist()
        if admin is not None:admin.close()
        print(artifact.name,report['result'],report['cleanup'],flush=True)
if __name__=='__main__':run()
