"""Remaining transaction workflows; marked owned loopback PostgreSQL only."""
import hashlib
import json
import threading
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL, ROOT, engine_for, trade_tests
from verify_transaction_pilot import read_tests
from actors import UserActor
from endpoints.transaction.workflow_service import TransactionWorkflowService
from endpoints.transaction.workflow_repository import TransactionWorkflowRepository
from endpoints.transaction.transactionModel import TransactionModel

FIXTURE = '''
DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "League" (id bigint PRIMARY KEY,commissioner bigint,settings jsonb,"tradeDeadline" timestamptz,"freeAgentDeadline" timestamptz);
INSERT INTO "League" VALUES (10,1,'{"roster":{"maxSwaps":5},"transactions":{"tradeVeto":{"enabled":true,"requiredVetoCount":2}}}',NULL,NULL),(20,2,'{}',NULL,NULL);
CREATE TABLE "User" (id bigint PRIMARY KEY,"displayName" text);
INSERT INTO "User" VALUES (1,'Alice'),(2,'Bob'),(3,'Voter Three'),(4,'Voter Four');
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint,"userId" bigint,"teamName" text);
INSERT INTO "LeagueMember" VALUES (11,10,1,'Alice Team'),(12,10,2,'Bob Team'),(13,10,3,'Third Team'),(14,10,4,'Fourth Team'),(21,20,2,'Private Team');
CREATE TABLE "Week" (id bigint PRIMARY KEY,"leagueId" bigint,"weekNumber" integer,"isLocked" boolean);
INSERT INTO "Week" VALUES (100,10,1,false),(101,10,2,false),(102,10,3,true),(200,20,1,false);
CREATE TABLE "SportTeam" (id bigint PRIMARY KEY,"displayName" text);
INSERT INTO "SportTeam" VALUES (101,'Alpha'),(102,'Beta'),(103,'Gamma'),(104,'Delta'),(105,'Epsilon');
CREATE TABLE "ConferenceMembership" ("sportTeamId" bigint,"sportConferenceId" bigint);
INSERT INTO "ConferenceMembership" VALUES (101,500),(102,500),(103,500),(104,501),(105,501);
CREATE TABLE "SportConference" (id bigint PRIMARY KEY,"maxTeamsPerOwner" integer);
INSERT INTO "SportConference" VALUES (500,3),(501,1);
CREATE TABLE "LeagueTeamSlot" (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"leagueId" bigint,"memberId" bigint,
 "sportTeamId" bigint,"acquiredWeek" integer,"droppedWeek" integer,"acquiredVia" text);
INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia")
 VALUES (10,11,101,1,'Draft'),(10,12,102,1,'Draft'),(10,13,104,1,'Draft'),(20,21,101,1,'Draft');
CREATE TABLE "Transaction" (id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,"leagueId" bigint,"weekId" bigint,type text,
 "memberFromId" bigint,"memberToId" bigint,status text,"fromTeamIds" jsonb,"toTeamIds" jsonb,
 "createdAt" timestamptz DEFAULT now(),"decidedByMemberId" bigint,"rejectReason" text);
CREATE TABLE "TransactionVote" ("transactionId" bigint,"leagueMemberId" bigint,veto boolean,PRIMARY KEY("transactionId","leagueMemberId"));
'''


def tests(engine,database):
    covered=set()
    def observe(name,method):
        def wrapped(self,*args):covered.add(name);return method(self,*args)
        return wrapped
    observed=type('ObservedWorkflowRepository',(TransactionWorkflowRepository,),{
        name:observe(name,method) for name,method in vars(TransactionWorkflowRepository).items()
        if callable(method) and not name.startswith('_')})
    service=TransactionWorkflowService(engine,observed());alice=UserActor(1,'alice');bob=UserActor(2,'bob')
    def query(statement, **params):
        with engine.begin() as conn:
            result=conn.execute(text(statement),params)
            return result.mappings().all() if result.returns_rows else []
    def reset():
        with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    def state():
        return {table:[dict(r) for r in query(f'SELECT * FROM "{table}" ORDER BY 1,2')]
            for table in ('League','LeagueMember','Week','Transaction','TransactionVote','LeagueTeamSlot')}
    def propose():return service.propose(alice,10,100,11,12,[101],[102])['transactionId']
    def free():return service.free_agency(alice,10,100,999,11,103,101)
    def expect(error,call,contains=None):
        try:call()
        except error as exc:
            if contains:assert contains in str(exc),(contains,str(exc))
        else:raise AssertionError('Expected '+error.__name__)
    def failure_after(fragment,call):
        before=state();triggered=[]
        def fail(conn,cursor,statement,params,context,many):
            if fragment in statement:triggered.append(True);raise RuntimeError('synthetic post-write failure')
        event.listen(engine,'after_cursor_execute',fail)
        try:expect(RuntimeError,call)
        finally:event.remove(engine,'after_cursor_execute',fail)
        assert triggered and state()==before,fragment
    reset();before=state();tx=propose()
    assert tx==1 and state()['Transaction'][0]['status']=='PROPOSED' and state()['LeagueTeamSlot']==before['LeagueTeamSlot']
    for call in (lambda:service.propose(bob,10,100,11,12,[101],[102]),lambda:service.respond(alice,10,tx,'ACCEPT',12),
                 lambda:service.respond(bob,20,tx,'ACCEPT',12),lambda:service.cancel(bob,10,tx,11)):
        before=state();expect(PermissionError,call);assert state()==before
    assert service.respond(bob,10,tx,'ACCEPT',12)=={'transactionId':tx,'status':'PENDING_APPLY'}
    assert service.apply_pending_for_job(tx) is None
    assert state()['Transaction'][0]['status']=='COMPLETED'
    expect(ValueError,lambda:service.apply_pending_for_job(tx),'not pending')
    reset();tx=propose();query('UPDATE "League" SET "tradeDeadline"=now()-interval \'1 second\' WHERE id=10')
    expect(ValueError,lambda:service.respond(bob,10,tx,'ACCEPT',12),'deadline')
    assert service.respond(bob,10,tx,'REJECT',12,'No thanks')['status']=='REJECTED'
    assert state()['Transaction'][0]['rejectReason']=='No thanks'
    reset();tx=propose();assert service.cancel(alice,10,tx,11)['status']=='CANCELLED'
    reset();tx=propose()
    assert service.veto(UserActor(3,'voter'),10,tx,13)['vetoCount']==1
    assert service.veto(UserActor(3,'voter'),10,tx,13)['vetoCount']==0
    service.veto(UserActor(3,'voter'),10,tx,13)
    assert service.veto(UserActor(4,'voter4'),10,tx,14)['status']=='VETOED'
    expect(ValueError,lambda:service.veto(UserActor(3,'voter'),10,tx,13),'not vetoable')
    # Actual LATERAL/JSON projection and personalized party/voter split.
    reset();tx=propose();service.veto(UserActor(3,'voter'),10,tx,13)
    other=service.propose(bob,10,100,12,13,[102],[104])['transactionId']
    mine=service.open_trades(alice,10,11)
    assert len(mine['mine']['outgoing'])==1 and mine['mine']['incoming']==[]
    row=mine['mine']['outgoing'][0]
    assert row['fromTeams']==[{'id':101,'displayName':'Alpha'}] and row['toTeams']==[{'id':102,'displayName':'Beta'}]
    assert row['memberFromDisplayName']=='Alice' and row['createdAt'] and row['vetoCount']==1
    assert [r['transactionId'] for r in mine['others']]==[other]
    voter=service.open_trades(UserActor(3,'voter'),10,13)
    assert next(r for r in voter['others'] if r['transactionId']==tx)['memberHasVetoed'] is True
    assert len(service.open_trades_for_job(10,11)['others'])==1
    # Free agent planning: effective stored week, pending arrays/conflicts, caps, deadline/swap.
    reset();before=state()['LeagueTeamSlot'];move=free()
    assert (move['weekId'],move['weekNumber'],move['memberRosterTeamIds'])==(100,1,[103])
    assert state()['LeagueTeamSlot']==before
    expect(ValueError,free,'pending add')
    expect(ValueError,lambda:service.free_agency(alice,10,100,1,11,None,101),'pending drop')
    service.apply_pending_for_job(move['transactionId'])
    assert state()['Transaction'][0]['status']=='COMPLETED'
    slots=state()['LeagueTeamSlot'];assert slots[0]['droppedWeek']==1
    assert any(r['sportTeamId']==103 and r['memberId']==11 and r['acquiredVia']=='FREE_AGENT' for r in slots)
    expect(ValueError,lambda:service.apply_free_agent_for_job(move['transactionId']),'not pending')
    reset();query('UPDATE "Week" SET "isLocked"=true WHERE id=100');move=free()
    assert (move['weekId'],move['weekNumber'])==(101,2)
    reset();query('UPDATE "League" SET "freeAgentDeadline"=now()-interval \'1 second\' WHERE id=10');before=state()
    expect(ValueError,free,'deadline');assert state()==before
    reset();query('UPDATE "SportConference" SET "maxTeamsPerOwner"=1 WHERE id=500')
    expect(ValueError,lambda:service.free_agency(alice,10,100,1,11,103,None),'maxTeamsPerOwner')
    reset();expect(ValueError,lambda:service.free_agency(alice,10,100,1,11,999,None),'Missing ConferenceMembership')
    expect(ValueError,lambda:service.free_agency(alice,10,100,1,11,None,102),'does not own')
    expect(ValueError,lambda:service.free_agency(alice,10,100,1,11,102,None),'not a free agent')
    reset();free();query('UPDATE "League" SET settings=jsonb_set(settings,\'{roster,maxSwaps}\',\'1\') WHERE id=10')
    expect(service.SwapLimitExceeded,free,'used 1/1')
    assert service.SwapLimitExceeded is TransactionModel.SwapLimitExceeded
    # Executemany for legacy multi-add rows; no new apply-time validation policy.
    reset();row=query('''INSERT INTO "Transaction" ("leagueId","weekId",type,"memberFromId",status,"fromTeamIds","toTeamIds")
        VALUES (10,100,'FREE_AGENT',11,'PENDING_APPLY','[101]','[103,105]') RETURNING id''')[0]
    service.apply_free_agent_for_job(row['id']);assert sum(r['memberId']==11 and r['acquiredVia']=='FREE_AGENT' for r in state()['LeagueTeamSlot'])==2
    reset();query('''INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek") VALUES (10,11,103,1)''')
    query('UPDATE "SportConference" SET "maxTeamsPerOwner"=1 WHERE id=500')
    assert service.get_week_roster_violations(10,100)[0]=={'memberId':11,'sportConferenceId':500,'count':2,'maxTeamsPerOwner':1}
    before=state();expect(ValueError,lambda:service.lock_week_for_job(10,100),'Roster violations');assert state()==before
    query('UPDATE "SportConference" SET "maxTeamsPerOwner"=3 WHERE id=500')
    assert service.lock_week_for_job(10,100)=={'message':'Week locked successfully','leagueId':10,'weekId':100}
    assert state()['Week'][0]['isLocked']
    # Mutation boundaries roll back within the existing scope.
    for action,fragment in (('propose','INSERT INTO "Transaction"'),('accept','UPDATE "Transaction"'),
        ('reject','UPDATE "Transaction"'),('cancel','UPDATE "Transaction"'),('free','INSERT INTO "Transaction"'),
        ('veto','INSERT INTO "TransactionVote"'),('toggle','UPDATE "TransactionVote"'),('threshold','SET status ='),
        ('apply_drop','UPDATE "LeagueTeamSlot"'),('apply_add','INSERT INTO "LeagueTeamSlot"'),('apply_mark','UPDATE "Transaction"')):
        reset();tx=None
        if action not in ('propose','free'):tx=propose()
        if action=='toggle':service.veto(UserActor(3,'voter'),10,tx,13)
        if action=='threshold':service.veto(UserActor(3,'voter'),10,tx,13)
        if action.startswith('apply_'):
            reset();tx=free()['transactionId']
        calls={'propose':propose,'free':free,'accept':lambda:service.respond(bob,10,tx,'ACCEPT',12),
            'reject':lambda:service.respond(bob,10,tx,'REJECT',12),'cancel':lambda:service.cancel(alice,10,tx,11),
            'veto':lambda:service.veto(UserActor(3,'voter'),10,tx,13),'toggle':lambda:service.veto(UserActor(3,'voter'),10,tx,13),
            'threshold':lambda:service.veto(UserActor(4,'voter4'),10,tx,14)}
        failure_after(fragment,(lambda:service.apply_free_agent_for_job(tx)) if action.startswith('apply_') else calls[action])
    for deferred in (False,True):
        reset();before=state()
        with engine.begin() as conn:
            conn.exec_driver_sql('''CREATE FUNCTION reject_tx() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'synthetic transaction failure'; END $$;''')
            if deferred:conn.exec_driver_sql('CREATE CONSTRAINT TRIGGER reject_tx AFTER INSERT ON "Transaction" DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION reject_tx()')
            else:conn.exec_driver_sql('CREATE TRIGGER reject_tx BEFORE INSERT ON "Transaction" FOR EACH ROW EXECUTE FUNCTION reject_tx()')
        expect(DBAPIError,propose);assert state()==before
    # Separate transaction revocation between action write and postcheck.
    reset();tx=propose();before=state();other=engine_for(database,'otm-workflow-revoker');changed=[]
    def revoke(conn,cursor,statement,params,context,many):
        if 'UPDATE "Transaction"' in statement and not changed:
            changed.append(True)
            with other.begin() as separate:separate.execute(text('UPDATE "LeagueMember" SET "userId"=2 WHERE id=11'))
    event.listen(engine,'after_cursor_execute',revoke)
    try:expect(PermissionError,lambda:service.cancel(alice,10,tx,11))
    finally:event.remove(engine,'after_cursor_execute',revoke);other.dispose()
    before['LeagueMember'][0]['userId']=2;assert changed==[True] and state()==before
    reset();propose();other=engine_for(database,'otm-workflow-read-revoker');changed=[]
    def revoke_read(conn,cursor,statement,params,context,many):
        if 'LEFT JOIN LATERAL' in statement and not changed:
            changed.append(True)
            with other.begin() as separate:separate.execute(text('UPDATE "LeagueMember" SET "userId"=2 WHERE id=11'))
    event.listen(engine,'before_cursor_execute',revoke_read)
    try:assert service.open_trades(alice,10,11)=={'memberId':11,'mine':{'incoming':[],'outgoing':[]},'others':[]}
    finally:event.remove(engine,'before_cursor_execute',revoke_read);other.dispose()
    assert changed==[True]
    # Observe real row-lock wait for concurrent cancellation, then reject replay.
    reset();tx=propose();locked=threading.Event();release=threading.Event();outcomes=[];other=engine_for(database,'otm-workflow-contender')
    def hold(conn,cursor,statement,params,context,many):
        if 'FOR UPDATE' in statement:locked.set();assert release.wait(8)
    def cancel(db):
        try:TransactionWorkflowService(db).cancel(alice,10,tx,11);outcomes.append('cancelled')
        except ValueError:outcomes.append('rejected')
        except BaseException as exc:outcomes.append(repr(exc))
    event.listen(engine,'after_cursor_execute',hold);first=threading.Thread(target=cancel,args=(engine,));second=threading.Thread(target=cancel,args=(other,))
    try:
        first.start();assert locked.wait(5);second.start()
        for _ in range(300):
            rows=query("SELECT wait_event_type FROM pg_stat_activity WHERE application_name='otm-workflow-contender'")
            if rows and rows[0]['wait_event_type']=='Lock':break
            threading.Event().wait(.01)
        else:raise AssertionError('Workflow lock wait not observed')
        release.set();first.join(5);second.join(5)
        assert not first.is_alive() and not second.is_alive() and sorted(outcomes)==['cancelled','rejected'],outcomes
    finally:
        release.set();first.join(5)
        if second.ident:second.join(5)
        event.remove(engine,'after_cursor_execute',hold);other.dispose()
    reset();legacy=TransactionModel.__new__(TransactionModel);legacy.db=engine
    assert legacy._get_week_for_league(10,100)['weekNumber']==1
    declared={name for name,method in vars(TransactionWorkflowRepository).items() if callable(method) and not name.startswith('_')}
    assert covered==declared,{'missing_native_workflow_queries':sorted(declared-covered)}
    return {'all33_workflow_operations_arrays_jsonb_lateral_executemany':'PASS',
        'actor_roles_ownership_status_deadline_swap_caps_pending_and_effective_week':'PASS',
        'proposal_accept_reject_cancel_veto_toggle_threshold_and_dispatch_apply_replay':'PASS',
        'personalized_party_voter_display_projection_and_query_time_revocation':'PASS',
        'mutation_phase_real_statement_deferred_commit_and_postwrite_authority_rollback':'PASS',
        'observed_concurrent_cancel_lock_wait_and_replay_rejection':'PASS',
        'roster_violations_unregistered_lock_helper_and_legacy_exception_identity':'PASS',
        'repository_queries_exercised':sorted(covered),
        'scope_limit':'Original helper connections, validation/revalidation, membership/cap rules and revocation boundary semantics preserved; no new routes/schema/timeout/startup policy.'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_transaction_complete_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-transaction-complete');workflows=tests(engine,name)
        trades=trade_tests(engine,name);reads=read_tests(engine,name)
        files=sorted(str(p.relative_to(ROOT)) for p in (ROOT/'api/endpoints/transaction').glob('*.py'))
        files+=['api/actors.py','api/utils/authorization.py','api/cronJobs/cronComputeWeeklyScores.py','api/tests/test_transaction_workflow_service.py',
            'scripts/modernization/verify_transaction_pilot.py','scripts/modernization/verify_transaction_complete.py']
        report={'result':'PASS','scope':'Marked uniquely owned loopback PostgreSQL; no configured app/DB/jobs startup','workflows':workflows,
            'original_trade_pilot_rerun':trades,'original_read_pilot_rerun':reads,
            'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-transaction-complete-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cursor:cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
