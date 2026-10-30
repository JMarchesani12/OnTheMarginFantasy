"""Weekly points on marked disposable PostgreSQL, never .env/configured DSN."""
import hashlib
import json
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text

from assess_postgres import LOCAL,ROOT,engine_for
from actors import UserActor
from endpoints.scoring.service import ScoringReadService
from endpoints.scoring.contracts import ScoringReadDenied
from endpoints.scoring.scoringModel import ScoringModel

FIXTURE='''
CREATE TABLE "League" (id bigint PRIMARY KEY,commissioner bigint);
INSERT INTO "League" VALUES (10,1),(20,3),(30,1);
CREATE TABLE "LeagueMember" (id bigint PRIMARY KEY,"leagueId" bigint,"userId" bigint,"teamName" text);
INSERT INTO "LeagueMember" VALUES (11,10,4,'Alpha'),(12,10,2,'Bob'),(21,20,3,'Other');
CREATE TABLE "Week" (id bigint PRIMARY KEY,"leagueId" bigint,"weekNumber" bigint,"startDate" date,"endDate" date);
INSERT INTO "Week" VALUES (90,10,0,'2026-09-01','2026-09-07'),
    (100,10,1,'2026-10-01','2026-10-07'),(200,20,1,'2026-10-01','2026-10-07');
CREATE TABLE "WeeklyTeamScore" ("leagueId" bigint,"weekId" bigint,"memberId" bigint,
    "pointsAwarded" numeric,"pointDifferential" bigint,rank bigint);
INSERT INTO "WeeklyTeamScore" VALUES (10,90,11,4,20,1),(10,100,11,2.5,10,1),
    (10,100,12,1,5,2),(20,200,21,99,99,1);
'''


def scoring_tests(engine,database):
    with engine.begin() as conn:
        conn.exec_driver_sql(FIXTURE)
    service=ScoringReadService(engine)
    for actor in (UserActor(1,'commissioner'),UserActor(2,'member')):
        rows=service.get_weekly_points(actor,10,[-1,'1',1,0])
        assert [(r['weekNumber'],r['memberId']) for r in rows]==[(0,11),(1,11),(1,12)],rows
        assert set(rows[0])=={'weekNumber','startDate','endDate','memberId','teamName','pointsAwarded','pointDifferential','rank'}
        assert rows[0]['startDate'].isoformat()=='2026-09-01'
        assert float(rows[1]['pointsAwarded'])==2.5
        assert service.get_weekly_points(actor,10,[])==[]
    assert service.get_weekly_points(UserActor(1,'commissioner'),30,[1])==[]
    for league,weeks in ((10,[1]),(10,[]),(10,[-2]),(999,[1])):
        try:
            service.get_weekly_points(UserActor(99,'outsider'),league,weeks)
        except ScoringReadDenied:
            pass
        else:
            raise AssertionError('Outsider read was allowed')
    assert ScoringModel(engine,None).get_weekly_points_awarded_for_league(20,[1])[0]['pointsAwarded']==99
    assert service.get_weekly_points_for_job(999,[])==[]
    revoker=engine_for(database,'otm-scoring-revoker')
    try:
        for empty in (False,True):
            revoked=False
            checks=0
            def before_query(conn,cursor,statement,params,context,many):
                nonlocal revoked,checks
                if 'SELECT id FROM "League"' in statement:
                    checks+=1
                trigger=(checks==2 if empty else 'WeeklyTeamScore' in statement)
                if trigger and not revoked:
                    revoked=True
                    with revoker.begin() as other:
                        other.execute(text('DELETE FROM "LeagueMember" WHERE id=12'))
            event.listen(engine,'before_cursor_execute',before_query)
            try:
                try:
                    service.get_weekly_points(UserActor(2,'member'),10,[] if empty else [1])
                except ScoringReadDenied:
                    pass
                else:
                    raise AssertionError('Revoked read returned private/empty success')
                assert revoked and checks==2,(revoked,checks)
            finally:
                event.remove(engine,'before_cursor_execute',before_query)
                with revoker.begin() as other:
                    other.execute(text('INSERT INTO "LeagueMember" VALUES (12,10,2,\'Bob\')'))
    finally:
        revoker.dispose()
    return {'expanding_week_bind_normalization_and_order':'PASS','native_projection_dates_and_numeric':'PASS',
            'league_isolation_and_member_commissioner_policy':'PASS','empty_list_access_policy':'PASS',
            'separate_connection_revocation_scores_and_empty_lists':'PASS','legacy_trusted_read':'PASS'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL)
    admin.autocommit=True
    name='otm_scoring_'+uuid4().hex
    created=False
    engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created=True
        engine=engine_for(name,'otm-scoring-read')
        results=scoring_tests(engine,name)
        files=['api/endpoints/scoring/'+f for f in ('service.py','repository.py','contracts.py','scoringModel.py','scoringEndpoints.py')]
        files+=['api/actors.py','api/utils/authorization.py','scripts/modernization/verify_scoring_read.py']
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database',
                'weekly_points':results,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-scoring-read-postgres-2026-10-29.json').write_text(json.dumps(report,indent=2)+'\n')
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
