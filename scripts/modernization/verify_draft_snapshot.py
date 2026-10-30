"""Draft snapshot native SQL/repair/transaction verification, synthetic DB only."""
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import event,text
from sqlalchemy.exc import DBAPIError
from assess_postgres import LOCAL,ROOT,engine_for
from actors import UserActor
from endpoints.draft.snapshot_service import DraftSnapshotService
from endpoints.draft.draftModel import DraftModel

FIXTURE = 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;\nCREATE TABLE "User" (id integer PRIMARY KEY,uuid text,email text,"displayName" text);\nINSERT INTO "User" VALUES (1,\'alice\',\'alice@example.test\',\'Alice\'),(2,\'bob\',\'bob@example.test\',\'Bob\');\n\n            INSERT INTO "User" (id, uuid, email, "displayName") VALUES\n                (3, \'00000000-0000-4000-8000-000000000003\', \'outsider@example.test\', \'Outsider\');\n            CREATE TABLE "League" (id INTEGER PRIMARY KEY, "numPlayers" INTEGER,\n                settings jsonb, "seasonYear" INTEGER, commissioner INTEGER, "isDiscoverable" BOOLEAN);\n            INSERT INTO "League" VALUES\n                (10, 2, \'{"draft":{"type":"snake","rounds":2}}\', 2026, 1, true),\n                (20, 1, \'{"draft":{"type":"linear","rounds":2}}\', 2026, 2, false),\n                (30, 1, \'{"draft":{"privateMarker":"hidden"}}\', 2026, 1, false);\n            CREATE TABLE "LeagueMember" (id INTEGER PRIMARY KEY, "leagueId" INTEGER,\n                "userId" INTEGER, "teamName" TEXT, "draftOrder" INTEGER);\n            INSERT INTO "LeagueMember" VALUES\n                (11, 10, 1, \'Alice Open\', 1), (12, 10, 2, \'Bob Open\', 2),\n                (21, 20, 2, \'Bob Private\', 1);\n            CREATE TABLE "DraftState" ("leagueId" INTEGER PRIMARY KEY, status TEXT,\n                "currentOverallPickNumber" INTEGER, "currentMemberId" INTEGER,\n                "expiresAt" timestamptz, "lastPickAt" timestamptz, "updatedAt" timestamptz);\n            INSERT INTO "DraftState" VALUES\n                (10, \'live\', 2, 12, \'2026-10-28T12:01:00Z\', \'2026-10-28T12:00:00Z\', \'2000-01-01T00:00:00Z\'),\n                (20, \'paused\', 1, 21, NULL, NULL, \'2000-01-01T00:00:00Z\'),\n                (30, \'complete\', 1, 11, \'2026-10-28T12:01:00Z\', NULL, \'2000-01-01T00:00:00Z\');\n            CREATE TABLE "DraftPick" (id INTEGER, "leagueId" INTEGER, "createdAt" timestamptz,\n                "overallPickNumber" INTEGER, "roundNumber" INTEGER, "pickInRound" INTEGER,\n                "memberId" INTEGER, "sportTeamId" INTEGER);\n            INSERT INTO "DraftPick" VALUES (1, 10, \'2026-10-28T12:00:00Z\', 1, 1, 1, 11, 101);\n            CREATE TABLE "DraftTurn" ("leagueId" INTEGER, "overallPickNumber" INTEGER, "memberId" INTEGER);\n            INSERT INTO "DraftTurn" VALUES (10, 1, 11), (10, 2, 12), (10, 3, 12), (10, 4, 11),\n                (20, 1, 21), (20, 2, 21);\n            CREATE TABLE "SportTeam" (id INTEGER, "sportId" INTEGER, "displayName" TEXT);\n            INSERT INTO "SportTeam" VALUES (101, 1, \'Synthetic Team\');\n            CREATE TABLE "ConferenceMembership" ("sportTeamId" INTEGER, "sportId" INTEGER,\n                "seasonYear" INTEGER, "sportConferenceId" INTEGER);\n            INSERT INTO "ConferenceMembership" VALUES (101, 1, 2026, 501);\n            CREATE TABLE "SportConference" (id INTEGER, "sportId" INTEGER, "conferenceId" INTEGER);\n            INSERT INTO "SportConference" VALUES (501, 1, 401);\n            CREATE TABLE "Conference" (id INTEGER, name TEXT);\n            INSERT INTO "Conference" VALUES (401, \'Synthetic Conference\');\n        '


def tests(engine,database):
    with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    service=DraftSnapshotService(engine);alice=UserActor(1,'alice')
    def state(league=10):
        with engine.connect() as conn:
            return dict(conn.execute(text('SELECT * FROM "DraftState" WHERE "leagueId"=:id'),{'id':league}).mappings().one())
    before=state(30)
    for actor,league in ((alice,30),(UserActor(3,'outsider'),10),(alice,999)):
        try:service.snapshot(actor,league)
        except PermissionError:pass
        else:raise AssertionError('Member-only snapshot scope bypass')
    assert state(30)==before
    try:service.snapshot_for_job(999)
    except ValueError:pass
    else:raise AssertionError('Trusted missing league guard')
    with engine.begin() as conn:
        conn.exec_driver_sql('''INSERT INTO "Conference" VALUES (402,'Old Conference'),(403,'Wrong Sport');
            INSERT INTO "SportConference" VALUES (502,1,402),(503,2,403);
            INSERT INTO "ConferenceMembership" VALUES (101,1,2025,502),(101,2,2026,503);''')
    row=service.snapshot(alice,10)
    assert set(row)=={'leagueId','draftSettings','serverNow','state','members','picks','onDeck','inTheHole'}
    assert row['draftSettings']=={'type':'snake','rounds':2} and row['serverNow'].endswith('+00:00')
    assert [r['memberId'] for r in row['members']]==[11,12]
    assert len(row['picks'])==1 and row['picks'][0]['conferenceName']=='Synthetic Conference'
    assert row['picks'][0]['createdAt'].tzinfo is not None and row['state']['expiresAt'].tzinfo is not None
    assert row['onDeck']=={'overallPickNumber':3,'memberId':12,'memberTeamName':'Bob Open'}
    assert row['inTheHole']=={'overallPickNumber':4,'memberId':11,'memberTeamName':'Alice Open'}
    with engine.begin() as conn:
        conn.exec_driver_sql('''INSERT INTO "SportTeam" VALUES (102,1,'Independent');
            INSERT INTO "DraftPick" VALUES (2,10,now(),3,2,1,12,102);
            DELETE FROM "DraftState" WHERE "leagueId"=20;''')
    row=service.snapshot(alice,10)
    assert row['onDeck']['overallPickNumber']==4 and row['inTheHole'] is None
    assert row['picks'][1]['conferenceName'] is None
    assert service.snapshot_for_job(20)['state'] is None
    with engine.begin() as conn:conn.execute(text('UPDATE "DraftState" SET status=\'complete\' WHERE "leagueId"=10'))
    before=state()
    def fail(conn,cursor,statement,params,context,many):
        if 'WITH league_info AS' in statement:raise RuntimeError('synthetic post-repair read failure')
    event.listen(engine,'after_cursor_execute',fail)
    try:
        try:service.snapshot(alice,10)
        except RuntimeError:pass
        else:raise AssertionError('Post-repair failure missing')
    finally:event.remove(engine,'after_cursor_execute',fail)
    assert state()==before
    with engine.begin() as conn:
        conn.exec_driver_sql('''CREATE FUNCTION fail_snapshot_commit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'synthetic deferred snapshot failure'; END $$;
            CREATE CONSTRAINT TRIGGER snapshot_commit AFTER UPDATE ON "DraftState"
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fail_snapshot_commit();''')
    try:service.snapshot(alice,10)
    except DBAPIError:pass
    else:raise AssertionError('Deferred repair failure missing')
    assert state()==before
    with engine.begin() as conn:conn.exec_driver_sql('DROP TRIGGER snapshot_commit ON "DraftState"')
    try:
        with engine.begin() as conn:
            row=service.snapshot(alice,10,conn=conn)
            assert row['state']['currentMemberId'] is None and row['state']['expiresAt'] is None
            raise RuntimeError('caller rollback')
    except RuntimeError:pass
    assert state()==before
    row=service.snapshot(alice,10)
    assert row['state']['currentMemberId'] is None and state()['expiresAt'] is None
    with engine.begin() as conn:
        conn.execute(text('UPDATE "DraftState" SET "currentMemberId"=12,"expiresAt"=now() WHERE "leagueId"=10'))
    before=state();other=engine_for(database,'otm-draft-snapshot-revoke');changed=[];statements=[]
    def revoke(conn,cursor,statement,params,context,many):
        statements.append(statement)
        if '"numPlayers", settings' in statement and not changed:
            changed.append(True)
            with other.begin() as separate:separate.execute(text('DELETE FROM "LeagueMember" WHERE id=12'))
    event.listen(engine,'before_cursor_execute',revoke)
    try:
        try:service.snapshot(UserActor(2,'bob'),10)
        except PermissionError:pass
        else:raise AssertionError('Revoked member snapshot accepted')
    finally:event.remove(engine,'before_cursor_execute',revoke);other.dispose()
    assert changed==[True] and len(statements)==1 and state()==before
    model=DraftModel.__new__(DraftModel);model.db=engine
    assert model.get_draft_state_snapshot(20)['members'][0]['memberId']==21
    helper=DraftModel.__new__(DraftModel)
    with engine.begin() as conn:
        assert helper.get_draft_state_snapshot(20,conn=conn)['state'] is None
        assert helper._get_next_unpicked_turn_from(conn,10,3)==(4,11)
    return {'member_only_scope_before_repair':'PASS','native_json_timestamps_picks_season_join_turn_skipping':'PASS',
            'missing_state_trusted_legacy_supplied_connection':'PASS','repair_post_read_commit_caller_rollback':'PASS',
            'separate_connection_pre_query_revocation':'PASS'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_draft_snapshot_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cur:
            cur.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cur.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-draft-snapshot');result=tests(engine,name)
        files=['api/endpoints/draft/'+f for f in ('snapshot_service.py','snapshot_repository.py','draftModel.py','draftEndpoints.py','routes.py')]
        files+=['api/actors.py','scripts/modernization/verify_draft_snapshot.py']
        report={'result':'PASS','scope':'Synthetic marked loopback PostgreSQL; no configured/hosted database','snapshot':result,
                'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-draft-snapshot-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cur:cur.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
