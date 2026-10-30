"""Four member schedule read queries on a uniquely owned marked loopback DB."""
import hashlib
import json
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy import event, text
from assess_postgres import LOCAL, ROOT, engine_for
from verify_schedule_calendar import FIXTURE as CALENDAR_FIXTURE, tests as calendar_tests
from rules.leagueRules import resolve_rules
from endpoints.schedule.read_service import ScheduleReadService
from endpoints.schedule.read_repository import ScheduleReadRepository
from endpoints.schedule.scheduleModel import ScheduleModel

FIXTURE = CALENDAR_FIXTURE + '''
ALTER TABLE "Week" ADD COLUMN "createdAt" timestamptz DEFAULT '2000-01-01T00:00Z';
INSERT INTO "Week" ("leagueId","weekNumber","startDate","endDate","isLocked","scoringComplete")
 VALUES (10,2,'2026-11-02T00:00Z','2026-11-08T23:59:59.999999Z',false,false);
INSERT INTO "SportSeason" VALUES (2,1,2025,'2025-11-02','2025-11-22',false,NULL);
CREATE TABLE "SportTeam" (id bigint PRIMARY KEY,"sportId" bigint,"displayName" text,tier integer);
INSERT INTO "SportTeam" VALUES (101,1,'Alpha',1),(102,1,'Beta',3),(103,1,'Gamma',NULL),
 (104,1,'Delta',2),(201,2,'Other Sport',100);
CREATE TABLE "LeagueTeamSlot" ("leagueId" bigint,"memberId" bigint,"sportTeamId" bigint,
 "acquiredWeek" integer,"droppedWeek" integer);
INSERT INTO "LeagueTeamSlot" VALUES (10,11,101,1,NULL),(10,12,102,1,NULL),
 (20,11,103,1,NULL),(10,11,104,3,NULL),(10,11,103,1,2);
CREATE TABLE "ConferenceMembership" ("sportTeamId" bigint,"sportId" bigint,"seasonYear" integer,"sportConferenceId" bigint);
CREATE TABLE "SportConference" (id bigint,"sportId" bigint,"conferenceId" bigint);
CREATE TABLE "Conference" (id bigint,name text);
INSERT INTO "Conference" VALUES (401,'Synthetic Conference');
INSERT INTO "SportConference" VALUES (501,1,401);
INSERT INTO "ConferenceMembership" VALUES (101,1,2026,501),(102,1,2026,501),(103,1,NULL,501);
INSERT INTO "SeasonPhase" VALUES (1,1,NULL,'2026-11-02T00:00Z','2026-11-09T00:00Z',
 '{"positiveOnly":true,"marginMultiplier":3}');
CREATE TABLE "GameResult" (id bigint PRIMARY KEY,"externalGameId" text,date timestamptz,sport bigint,
 "sportSeasonId" bigint,"homeTeamId" bigint,"awayTeamId" bigint,"homeTeamName" text,"awayTeamName" text,
 "homeScore" integer,"awayScore" integer,broadcast text,"seasonPhaseId" bigint);
INSERT INTO "GameResult" VALUES
 (1,'e1','2026-11-02T00:00Z',1,1,101,102,'Alpha','Beta',21,0,'Test TV',NULL),
 (2,'e2','2026-11-03T12:00Z',1,1,102,101,'Beta','Alpha',0,21,NULL,NULL),
 (3,'e3','2026-11-04T12:00Z',1,1,101,102,'Alpha','Beta',21,0,NULL,1),
 (4,'e4','2026-11-05T12:00Z',1,1,101,102,'Alpha','Beta',0,21,NULL,1),
 (5,'e5','2026-11-06T12:00Z',1,1,101,103,'Alpha','Gamma',21,0,NULL,NULL),
 (6,'e6','2026-11-08T23:59:59.999999Z',1,1,101,102,'Alpha','Beta',0,0,NULL,NULL),
 (7,'after','2026-11-09T00:00Z',1,1,101,102,'Alpha','Beta',21,0,NULL,NULL),
 (8,'before','2026-11-01T23:59:59.999999Z',1,1,101,102,'Alpha','Beta',21,0,NULL,NULL),
 (9,'other-season','2026-11-03T12:00Z',1,2,101,102,'Alpha','Beta',21,0,NULL,NULL),
 (10,'other-sport','2026-11-03T12:00Z',2,1,101,102,'Alpha','Beta',21,0,NULL,NULL),
 (11,'unowned','2026-11-03T12:00Z',1,1,103,104,'Gamma','Delta',21,0,NULL,NULL);
'''


def tests(engine):
    covered=set()
    def observe(name, method):
        def wrapped(self,*args):
            covered.add(name)
            return method(self,*args)
        return wrapped
    observed=type('ObservedReadRepository',(ScheduleReadRepository,),{
        name:observe(name,method) for name,method in vars(ScheduleReadRepository).items()
        if callable(method) and not name.startswith('_')})
    service=ScheduleReadService(engine,observed())
    def query(statement, **params):
        with engine.begin() as conn:
            result=conn.execute(text(statement),params)
            return result.mappings().all() if result.returns_rows else []
    def reset():
        with engine.begin() as conn:conn.exec_driver_sql(FIXTURE)
    def state():
        return {table:query(f'SELECT * FROM "{table}" ORDER BY 1') for table in
                ('League','Week','LeagueTeamSlot','SportTeam','GameResult')}
    def expect(error,call):
        try:call()
        except error:pass
        else:raise AssertionError('Expected '+error.__name__)
    reset();before=state();games=service.member_games_for_job(10,11,2)
    assert [g['id'] for g in games]==[1,2,3,4,5,6]
    assert [g['memberPointDiff'] for g in games]==[11,11,33,0,11,0]
    assert games[1]['ownsAway'] is True and games[1]['rawMemberPointDiff']==21
    assert games[0]['broadcast']=='Test TV' and games[1]['broadcast'] is None
    assert games[4]['awayTeamTier']==4 and games[4]['awayTeamUnranked'] is True
    assert games[2]['tournamentAdjustment']=={'positiveOnly':True,'multiplier':3,'scoringMargin':33}
    assert state()==before
    opponent=service.member_games_for_job(10,12,2);assert opponent[0]['rawMemberPointDiff']==-21 and opponent[0]['memberPointDiff']==-11
    h2h=service.head_to_head_for_job(10,11,12,2);assert [g['id'] for g in h2h]==[1,2,3,4,6]
    assert h2h[0]['homeOwnedByA'] and h2h[0]['awayOwnedByB']
    reverse=service.head_to_head_for_job(10,12,11,2);assert reverse[0]['homeOwnedByB'] and reverse[0]['awayOwnedByA']
    week=service.week_for_job(10,2);assert week['weekNumber']==2 and week['leagueId']==10 and week['createdAt'] is not None
    assert set(week)=={'id','createdAt','leagueId','weekNumber','startDate','endDate','isLocked','scoringComplete'}
    owned=service.owned_teams_for_job(10,11,2);assert owned==[{'teamId':101,'teamName':'Alpha','tier':1,'sportConferenceId':501,'conferenceName':'Synthetic Conference'}]
    previous=service.owned_teams_for_job(10,11,1);assert [r['teamId'] for r in previous]==[101,103] and previous[1]['tier']==4
    future=service.owned_teams_for_job(10,11,3);assert [r['teamId'] for r in future]==[101,104]
    assert service.week_for_job(10,99) is None and service.member_games_for_job(10,11,99)==[]
    assert service.head_to_head_for_job(10,11,12,99)==[] and service.owned_teams_for_job(10,999,2)==[]
    query('INSERT INTO "LeagueTeamSlot" VALUES (10,11,102,2,NULL)')
    double=service.member_games_for_job(10,11,2)
    assert all(g['memberPointDiff']==0 and not g['tierAdjustment']['applied'] for g in double if g['id'] in (1,2,3,4,6))
    # Existing week fallback differs for H2H: preserve its NULL-start empty projection.
    reset();query('UPDATE "Week" SET "startDate"=NULL')
    assert len(service.member_games_for_job(10,11,2))==6 and service.week_for_job(10,2)['startDate'] is not None
    assert service.head_to_head_for_job(10,11,12,2)==[]
    # Owned-team projection deliberately retains original unrestricted-season membership join.
    reset();query('INSERT INTO "ConferenceMembership" VALUES (101,1,2025,501)')
    assert len(service.owned_teams_for_job(10,11,2))==2
    reset();query('UPDATE "League" SET settings=\'{"ruleSetVersion":"unknown"}\'')
    expect(ValueError,lambda:service.member_games_for_job(10,11,99))
    assert len(service.member_games_for_job(10,11,2,resolve_rules(1,{})))==6
    # Preserve original unfinished-score failure propagation; this extraction adds no score policy.
    reset();query('UPDATE "GameResult" SET "homeScore"=NULL WHERE id=1');before=state()
    expect(TypeError,lambda:service.member_games_for_job(10,11,2));assert state()==before
    reset();before=state();triggered=[]
    def fail(conn,cursor,statement,params,context,many):
        if 'rawMemberPointDiff' in statement:triggered.append(True);raise RuntimeError('synthetic read failure')
    event.listen(engine,'after_cursor_execute',fail)
    try:expect(RuntimeError,lambda:service.member_games_for_job(10,11,2))
    finally:event.remove(engine,'after_cursor_execute',fail)
    assert triggered==[True] and state()==before
    legacy=ScheduleModel.__new__(ScheduleModel);legacy.db=engine
    assert len(legacy.get_member_games_for_week(10,11,2))==6 and legacy.get_week_for_league(10,2)['weekNumber']==2
    declared={'member_games','head_to_head_games','week','owned_teams'}
    assert declared <= vars(ScheduleReadRepository).keys() and covered==declared
    return {'native_member_ownership_week_season_sport_filters_and_order':'PASS',
            'tier_perspectives_unranked_double_owned_and_tournament_math':'PASS',
            'head_to_head_directions_week_and_owned_plain_projections':'PASS',
            'acquisition_drop_boundaries_missing_rows_and_read_no_writes':'PASS',
            'supplied_invalid_rules_failure_propagation_and_legacy_db_only':'PASS',
            'original_null_start_h2h_null_score_and_membership_join_behavior':'PASS',
            'repository_queries_exercised':sorted(covered),
            'scope_limit':'Member reads only; original query/policy/failure semantics preserved. Other views/search, ingestion/bootstrap and final composition remain.'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_schedule_member_reads_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'otm-schedule-member-reads');calendar=calendar_tests(engine);result=tests(engine)
        files=['api/endpoints/schedule/'+f for f in ('read_service.py','read_repository.py','calendar_service.py','calendar_repository.py','scheduleModel.py','scheduleEndpoints.py','routes.py','helpers/weekHelper.py')]
        files+=['api/rules/leagueRules.py','api/rules/tournamentRules.py','api/tests/test_schedule_read_service.py','scripts/modernization/verify_schedule_calendar.py','scripts/modernization/verify_schedule_member_reads.py']
        report={'result':'PASS','scope':'Marked owned synthetic loopback PostgreSQL; no configured app/DB/provider/jobs startup',
                'member_reads':result,'calendar_rerun':calendar,'sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}}
        (ROOT/'docs/modernization/evidence/mod-038-schedule-member-reads-postgres-2026-10-30.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cursor:cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()

if __name__=='__main__':main()
