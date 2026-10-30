"""Profile read/update on marked disposable loopback PostgreSQL, never .env/DSN."""
import hashlib
import json
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from assess_postgres import LOCAL, ROOT, engine_for
from actors import UserActor
from endpoints.user.service import UserService
from endpoints.user.contracts import ProfileAccessDenied, ProfileNotFound, ProfileUpdateRejected
from endpoints.user.userModel import UserModel

ALICE='00000000-0000-4000-8000-000000000001'
BOB='00000000-0000-4000-8000-000000000002'

FIXTURE='''
CREATE TABLE "User" (id bigint PRIMARY KEY,uuid uuid UNIQUE,email text UNIQUE,
    "displayName" text,"createdAt" timestamptz DEFAULT '2026-01-01T00:00:00Z');
INSERT INTO "User" (id,uuid,email,"displayName") VALUES
    (1,'00000000-0000-4000-8000-000000000001','alice@example.test','Alice'),
    (2,'00000000-0000-4000-8000-000000000002','bob@example.test','Bob');
CREATE FUNCTION fail_profile_statement() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW."displayName" = 'fail-statement' THEN
        RAISE EXCEPTION 'synthetic statement failure';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER profile_statement_guard BEFORE UPDATE ON "User"
    FOR EACH ROW EXECUTE FUNCTION fail_profile_statement();
CREATE FUNCTION fail_profile_commit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW."displayName" = 'fail-commit' THEN
        RAISE EXCEPTION 'synthetic deferred commit failure';
    END IF;
    RETURN NEW;
END $$;
CREATE CONSTRAINT TRIGGER profile_commit_guard AFTER UPDATE ON "User"
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_profile_commit();
'''


def profile_tests(engine):
    with engine.begin() as conn:
        conn.exec_driver_sql(FIXTURE)
    service=UserService(engine)
    actor=UserActor(1,ALICE)
    original=service.get_profile(actor,1)
    assert set(original)=={'id','uuid','email','displayName','createdAt'},original
    assert str(original['uuid'])==ALICE and original['email']=='alice@example.test',original
    changed=service.update_profile(actor,1,{'displayName':"O'Connor; --",'uuid':BOB,'email':'forged@example.test','id':2})
    assert changed=={**original,'displayName':"O'Connor; --"},changed
    assert service.get_profile_for_job(2)['displayName']=='Bob'
    for operation,args in ((service.get_profile,(2,)),(service.update_profile,(2,{'displayName':'forged'}))):
        try:
            operation(actor,*args)
        except ProfileAccessDenied:
            pass
        else:
            raise AssertionError('Foreign profile was allowed')
    try:
        service.update_profile(actor,1,{'uuid':BOB})
    except ProfileUpdateRejected:
        pass
    else:
        raise AssertionError('Identity-only update was allowed')
    for name in ('fail-statement','fail-commit'):
        try:
            service.update_profile(actor,1,{'displayName':name})
        except DBAPIError:
            pass
        else:
            raise AssertionError('Synthetic native database failure did not abort')
        assert service.get_profile(actor,1)==changed,'Failed update changed stored profile'
    try:
        service.get_profile(UserActor(999,'missing'),999)
    except ProfileNotFound:
        pass
    else:
        raise AssertionError('Missing profile was not reported')
    model=UserModel(engine)
    assert model.get_user_by_id(2)['displayName']=='Bob'
    assert model.update_user(2,{'displayName':'Trusted'})['displayName']=='Trusted'
    assert model.get_user_by_uuid(BOB)['id']==2
    try:
        model.get_user_by_id(999)
    except ValueError:
        pass
    else:
        raise AssertionError('Legacy missing profile did not raise ValueError')
    return {'projection_and_identity_fields':'PASS','own_update_and_bound_parameters':'PASS',
            'foreign_and_invalid_update_denials':'PASS','statement_failure_rollback':'PASS',
            'deferred_commit_failure_rollback':'PASS','missing_profile_and_legacy_facade':'PASS'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL)
    admin.autocommit=True
    name='otm_profile_'+uuid4().hex
    created=False
    engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created=True
        engine=engine_for(name,'otm-profile-pilot')
        results=profile_tests(engine)
        files=['api/endpoints/user/'+f for f in ('service.py','repository.py','contracts.py','userModel.py','userEndpoints.py')]
        files+=['api/actors.py','api/authenticatedPrincipal.py','scripts/modernization/verify_profile_pilot.py']
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL, no configured/hosted database',
                'profile_reads_updates':results,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-profile-postgres-2026-10-29.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            with admin.cursor() as cur:
                cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()


if __name__=='__main__':
    main()
