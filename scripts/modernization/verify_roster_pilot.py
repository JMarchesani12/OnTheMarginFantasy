"""Native roster SQL on marked disposable loopback PostgreSQL, no .env/DSN."""
import hashlib
import json
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text

from assess_postgres import LOCAL, ROOT, engine_for
from actors import UserActor
from endpoints.roster.service import RosterService
from endpoints.roster.contracts import RosterAccessDenied, RosterWeekUnavailable


FIXTURE = '''
CREATE TABLE "League" (id bigint,commissioner bigint,sport bigint,"seasonYear" bigint);
INSERT INTO "League" VALUES (10,1,1,2026),(20,2,1,2026);
CREATE TABLE "LeagueMember" (id bigint,"leagueId" bigint,"userId" bigint);
INSERT INTO "LeagueMember" VALUES (12,10,2),(21,20,2);
CREATE TABLE "Week" (id bigint,"leagueId" bigint,"weekNumber" bigint,"isLocked" boolean);
INSERT INTO "Week" VALUES (100,10,1,true),(101,10,2,false),(200,20,1,false);
CREATE TABLE "LeagueTeamSlot" (id bigint,"leagueId" bigint,"memberId" bigint,"sportTeamId" bigint,
    "acquiredWeek" bigint,"droppedWeek" bigint,"acquiredVia" text);
INSERT INTO "LeagueTeamSlot" VALUES (1,10,12,101,1,NULL,'draft'),(2,10,12,105,1,2,'draft');
CREATE TABLE "SportTeam" (id bigint,"displayName" text,tier bigint,"sportId" bigint,"externalId" text,"schoolId" bigint);
INSERT INTO "SportTeam" VALUES (101,'Alpha',1,1,'a',1),(102,'Available',NULL,1,'b',2),
    (103,'Reserved',3,1,'c',3),(104,'Other sport',99,2,'d',4),(105,'Dropped',2,1,'e',5);
CREATE TABLE "ConferenceMembership" ("sportTeamId" bigint,"sportId" bigint,"seasonYear" bigint,"sportConferenceId" bigint);
INSERT INTO "ConferenceMembership" VALUES (101,1,2026,500),(101,1,2025,501),(102,1,2026,500),(105,1,NULL,500);
CREATE TABLE "SportConference" (id bigint,"sportId" bigint,"conferenceId" bigint);
INSERT INTO "SportConference" VALUES (500,1,600),(501,1,601);
CREATE TABLE "Conference" (id bigint,name text);
INSERT INTO "Conference" VALUES (600,'Current'),(601,'Old');
CREATE TABLE "Transaction" ("leagueId" bigint,"weekId" bigint,status text,type text,"toTeamIds" jsonb,"fromTeamIds" jsonb);
INSERT INTO "Transaction" VALUES (10,101,'PENDING_APPLY','FREE_AGENT','[103]','[101]'),
    (10,100,'PENDING_APPLY','FREE_AGENT','[102]',NULL),(10,101,'CANCELLED','FREE_AGENT','[102]',NULL);
'''


def roster_tests(engine, database):
    with engine.begin() as conn:
        conn.exec_driver_sql(FIXTURE)
    service = RosterService(engine)
    for actor in (UserActor(1,'commissioner'), UserActor(2,'member')):
        member = service.get_member_teams_for_week(actor,10,12,1)
        assert [r['sportTeamId'] for r in member] == [101], member
        assert member[0]['conferenceName'] == 'Current', member
        assert set(member[0]) == {'slotId','sportTeamId','acquiredWeek','droppedWeek',
            'acquiredVia','displayName','tier','externalId','sportConferenceId','conferenceName'}, member
        available = service.get_available_teams_for_week(actor,10,1)
        assert [r['id'] for r in available] == [101,102,105], available
        assert available[1]['tier'] == 4 and available[1]['conferenceName'] == 'Current', available
    for operation,args in ((service.get_member_teams_for_week,(10,12,1)),
                           (service.get_available_teams_for_week,(10,1))):
        try:
            operation(UserActor(3,'outsider'),*args)
        except RosterAccessDenied:
            pass
        else:
            raise AssertionError('Outsider was allowed')
    assert service.get_available_teams_for_job(999,1) == []
    revoker = engine_for(database, 'otm-roster-revoker')
    try:
        for marker, actor, operation,args in (
                ('WITH league_info',UserActor(2,'member'),service.get_member_teams_for_week,(10,12,1)),
                ('WITH pending_adds',UserActor(2,'member'),service.get_available_teams_for_week,(10,1)),
                ('WITH league_info',UserActor(1,'commissioner'),service.get_member_teams_for_week,(10,12,1))):
            revoked = False
            def before_data(conn,cursor,statement,params,context,many):
                nonlocal revoked
                if marker in statement and not revoked:
                    revoked=True
                    with revoker.begin() as other:
                        other.execute(text('DELETE FROM "LeagueMember" WHERE id=12'))
            event.listen(engine,'before_cursor_execute',before_data)
            try:
                assert operation(actor,*args) == []
                assert revoked
            finally:
                event.remove(engine,'before_cursor_execute',before_data)
                with revoker.begin() as other:
                    other.execute(text('INSERT INTO "LeagueMember" VALUES (12,10,2)'))
    finally:
        revoker.dispose()
    with engine.begin() as conn:
        conn.execute(text('DELETE FROM "Week" WHERE id=101'))
    for operation,args in ((service.get_member_teams_for_week,(10,12,1)),
                           (service.get_available_teams_for_week,(10,1))):
        try:
            operation(UserActor(1,'commissioner'),*args)
        except RosterWeekUnavailable:
            pass
        else:
            raise AssertionError('Missing future week did not fail')
    return {'locked_week_and_pending_moves': 'PASS','native_projection_seasonal_conferences_and_tiers': 'PASS',
            'member_commissioner_and_denials': 'PASS','query_time_revocation_and_target_removal': 'PASS',
            'missing_future_week': 'PASS'}


def main():
    admin = psycopg2.connect(dbname='postgres', **LOCAL)
    admin.autocommit=True
    name='otm_roster_'+uuid4().hex
    created=False
    engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
            created=True
        engine=engine_for(name,'otm-roster-pilot')
        results=roster_tests(engine,name)
        files=['api/endpoints/roster/'+f for f in ('service.py','repository.py','contracts.py','rosterModel.py','rosterEndpoints.py')]
        files+=['api/actors.py','api/utils/authorization.py','scripts/modernization/verify_roster_pilot.py']
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL, no configured/hosted database',
                'roster_reads':results,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-roster-postgres-2026-10-29.json').write_text(json.dumps(report,indent=2)+'\n')
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
