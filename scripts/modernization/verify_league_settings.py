"""League PATCH verification on marked synthetic PostgreSQL; no configured DSN."""
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL,ROOT,engine_for
from verify_league_delete import listing_tests,creation_tests,approval_tests,profile_tests,removal_tests,tests as deletion_tests
from actors import UserActor
from endpoints.league.league_admin_service import LeagueAdminService
from endpoints.league.leagueModel import LeagueModel

FIXTURE='''DROP SCHEMA public CASCADE; CREATE SCHEMA public;
CREATE TABLE "Sport" (id bigint PRIMARY KEY,name text);
INSERT INTO "Sport" VALUES (1,'Basketball');
CREATE TABLE "League" (id bigint PRIMARY KEY,"createdAt" timestamptz DEFAULT now(),name text,sport bigint,
    "numPlayers" integer,status text,settings jsonb,"updatedAt" timestamptz,"draftDate" timestamptz,
    "tradeDeadline" timestamptz,"freeAgentDeadline" timestamptz,commissioner bigint);
INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner) VALUES
    (10,'Alice League',1,8,'Pre-Draft','{"ruleSetVersion":"v1","timezone":"UTC","oldSetting":true}',1),
    (20,'Bob League',1,8,'Pre-Draft','{"ruleSetVersion":"v1","timezone":"UTC"}',2);'''


def tests(engine,database):
    service=LeagueAdminService(engine);actor=UserActor(1,'alice')
    def reset():
        with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    def state():
        with engine.connect() as conn:return [dict(r._mapping) for r in conn.execute(text('SELECT * FROM "League" ORDER BY id'))]
    reset();before=state()
    for who,league,patch,error in ((UserActor(2,'bob'),10,{'settings':[]},PermissionError),
            (actor,999,{'settings':[]},ValueError),(actor,10,{},ValueError),(actor,10,{'commissioner':2},ValueError),
            (actor,10,{'settings':[]},ValueError),(actor,10,{'settings':{'ruleSetVersion':'v2'}},ValueError),
            (actor,10,{'settings':{'schedule':{'timezone':'Invalid/Zone'},'timezone':'UTC'}},ValueError)):
        try:service.update(who,league,patch)
        except error:pass
        else:raise AssertionError('Authority/validation rejection missing')
        assert state()==before
    proposed={'schedule':{'timeZone':'America/Chicago'},'bonuses':{}}
    patch={'name':"O'Brien :name; --",'settings':proposed,'numPlayers':10,'status':'Pre-Draft',
           'draftDate':'2026-11-01T12:00:00Z','tradeDeadline':None,'freeAgentDeadline':'2027-01-01T12:00:00Z',
           'sport':2,'commissioner':2,'unknown':'ignored'}
    snapshot=json.loads(json.dumps(patch));row=service.update(actor,10,patch)
    assert patch==snapshot
    assert set(row)=={'id','createdAt','name','sport','numPlayers','status','settings','updatedAt','draftDate',
                      'freeAgentDeadline','tradeDeadline','commissioner','sportinfo'}
    assert row['sportinfo']=={'id':1,'name':'Basketball'}
    assert (row['name'],row['numPlayers'],row['sport'],row['commissioner'])==("O'Brien :name; --",10,1,1)
    assert row['settings']=={'schedule':{'timeZone':'America/Chicago'},'bonuses':{},'ruleSetVersion':'v1'}
    assert row['createdAt']==before[0]['createdAt'] and row['updatedAt'] is not None
    assert row['draftDate'].isoformat()=='2026-11-01T12:00:00+00:00' and row['tradeDeadline'] is None
    assert row['freeAgentDeadline'].isoformat()=='2027-01-01T12:00:00+00:00'
    assert state()[1]==before[1]

    # Failure paths retain the original operational exceptions and write rollback.
    for trusted in (False,True):
        reset();before=state()
        def update(patch):
            return service.update_for_job(10,patch) if trusted else service.update(actor,10,patch)
        try:update({'numPlayers':'not-an-integer'})
        except DBAPIError:pass
        else:raise AssertionError('Real integer statement failure missing')
        assert state()==before
        def fail(conn,cursor,statement,params,context,many):
            if 'WITH updated AS' in statement:raise RuntimeError('synthetic post-update failure')
        event.listen(engine,'after_cursor_execute',fail)
        try:
            try:update({'name':'Failed'})
            except RuntimeError:pass
            else:raise AssertionError('Post-update failure missing')
        finally:event.remove(engine,'after_cursor_execute',fail)
        assert state()==before
        with engine.begin() as conn:
            conn.exec_driver_sql('''CREATE FUNCTION fail_settings_commit() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RAISE EXCEPTION 'synthetic deferred settings failure'; END $$;
                CREATE CONSTRAINT TRIGGER settings_commit AFTER UPDATE ON "League"
                DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_settings_commit();''')
        try:update({'name':'Failed commit'})
        except DBAPIError:pass
        else:raise AssertionError('Deferred update failure missing')
        assert state()==before

    revoked=[]
    for facade in (False,True):
        reset();before=state();other=engine_for(database,'otm-settings-revoke');observed=[]
        def revoke(conn,cursor,statement,params,context,many):
            if 'SELECT id, sport, settings, commissioner' in statement and not observed:
                observed.append(True)
                with other.begin() as separate:
                    separate.execute(text('UPDATE "League" SET commissioner=2 WHERE id=10'))
        event.listen(engine,'after_cursor_execute',revoke)
        try:
            try:
                if facade:
                    model=LeagueModel.__new__(LeagueModel);model.db=engine
                    model.update_league_as_commissioner(10,1,{'name':'Stale'})
                else:service.update(actor,10,{'name':'Stale'})
            except PermissionError:pass
            else:raise AssertionError('Late commissioner change allowed mutation')
        finally:event.remove(engine,'after_cursor_execute',revoke);other.dispose()
        assert observed==[True]
        before[0]['commissioner']=2;assert state()==before
        revoked.append({'path':'legacy_facade' if facade else 'service','separate_connection_change_after_read':True,'rejected':'PermissionError'})

    # Preserve empty-result guards, including original commit-before-result-check semantics.
    empty=[]
    for trusted in (False,True):
        reset()
        with engine.begin() as conn:conn.exec_driver_sql('DELETE FROM "Sport"')
        try:
            if trusted:service.update_for_job(10,{'name':'Written before empty join'})
            else:service.update(actor,10,{'name':'Written before empty join'})
        except (PermissionError,RuntimeError) as exc:
            assert type(exc) is (RuntimeError if trusted else PermissionError)
        else:raise AssertionError('Empty Sport projection guard missing')
        assert state()[0]['name']=='Written before empty join'
        empty.append({'path':'trusted' if trusted else 'checked','empty_sport_join':'existing post-commit guard preserved'})
    reset();model=LeagueModel.__new__(LeagueModel);model.db=engine
    assert model.update_league(20,{'name':'Trusted'})['name']=='Trusted'
    assert model._update_league(10,{'name':'Private'})['name']=='Private'
    assert model._get_timezone_name_from_settings({'schedule':{'timeZone':'UTC'},'timezone':'Invalid'})=='UTC'
    assert model._ensure_timezone_in_settings({})=={'timezone':'UTC'}
    return {'authority_validation_order_input_immutability':'PASS','native_cte_json_projection_deadlines_bound_fields':'PASS',
            'real_statement_post_update_commit_rollback':'PASS','late_commissioner_revocation':revoked,
            'legacy_trusted_private_timezone_compatibility':'PASS','empty_result_compatibility':empty}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_league_settings_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-league-settings')
        prior={'listing_cancellation':listing_tests(engine,name),'creation_denial':creation_tests(engine,name),
               'approval':approval_tests(engine,name),'member_profile':profile_tests(engine,name),'member_removal':removal_tests(engine,name),'league_deletion':deletion_tests(engine,name)}
        settings=tests(engine,name)
        files=['api/endpoints/league/'+f for f in ('league_admin_service.py','league_admin_repository.py','member_service.py','member_repository.py','admission_service.py','admission_repository.py','contracts.py','leagueModel.py','leagueEndpoints.py')]
        files+=['api/actors.py','api/rules/leagueRules.py']+['scripts/modernization/'+f for f in ('verify_admission_slice.py','verify_admission_create_deny.py','verify_admission_approval.py','verify_member_profile.py','verify_member_removal.py','verify_league_delete.py','verify_league_settings.py')]
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','prior_slices_rerun':prior,
                'league_settings':settings,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-league-settings-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
