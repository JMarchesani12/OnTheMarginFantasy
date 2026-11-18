"""MOD-015 effective membership and write guards on owned marked PostgreSQL."""
import hashlib,json
from uuid import uuid4
import psycopg2
from psycopg2 import sql
from sqlalchemy import text
from assess_postgres import LOCAL,ROOT,engine_for
from actors import UserActor
from endpoints.roster.repository import RosterRepository
from endpoints.schedule.read_repository import ScheduleReadRepository
from endpoints.schedule.ingestion_repository import ScheduleIngestionRepository
from endpoints.draft.pick_repository import DraftPickRepository
from endpoints.draft.pick_service import DraftPickService
from endpoints.draft.snapshot_repository import DraftSnapshotRepository
from endpoints.league.reads.repository import LeagueReadRepository
from endpoints.transaction.repository import TransactionRepository
from endpoints.transaction.workflow_repository import TransactionWorkflowRepository
from endpoints.transaction.workflow_service import TransactionWorkflowService
from verify_mod010 import full_tests as prior_ownership_tests
from verify_draft_complete import tests as prior_draft_tests, snapshot_tests, finalize_tests, control_tests, order_tests
from verify_transaction_complete import tests as prior_transaction_tests
from verify_schedule_complete import tests as prior_schedule_tests, view_tests, member_tests, calendar_tests
from verify_roster_pilot import roster_tests as prior_roster_tests
SEED = 'INSERT INTO "User" (id,email) VALUES (1,\'alice@example.test\'),(2,\'bob@example.test\');\n            INSERT INTO "Sport" (id,name,"maxDraftRounds") VALUES (1,\'Basketball\',4),(2,\'Football\',4);\n            INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES\n            (1,1,2026,\'2026-01-01\',\'2026-10-31\'),(2,2,2026,\'2026-01-01\',\'2026-10-31\');\n            INSERT INTO "League" (id,name,sport,"numPlayers",status,settings,commissioner,"seasonYear") VALUES\n            (10,\'First\',1,2,\'In-Season\',\'{"bonuses":{"playoffDepth":{"first":3,"second":2},"conferenceChampion":{"first":2},"conferenceBottom":{"last":-1}}}\',1,2026),\n            (20,\'Same season\',1,1,\'In-Season\',\'{}\',2,2026),(30,\'Other season\',2,1,\'In-Season\',\'{}\',1,2026),\n            (40,\'Other year\',1,1,\'Pre-Draft\',\'{}\',1,2027);\n            INSERT INTO "LeagueMember" (id,"leagueId","userId","teamName","draftOrder") VALUES\n            (11,10,1,\'A\',1),(12,10,2,\'B\',2),(21,20,2,\'Same\',1),(31,30,1,\'Other\',1);\n            INSERT INTO "School" (id,name) VALUES (1,\'Synthetic\');\n            INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName",tier) VALUES (101,1,1,\'A\',1),(102,1,1,\'B\',1),(103,1,1,\'C\',1),(201,1,2,\'Other\',1);\n            INSERT INTO "Conference" (id,name) VALUES (1,\'Conference\');\n            INSERT INTO "SportConference" (id,"conferenceId","sportId","maxTeamsPerOwner") VALUES (500,1,1,3);\n            INSERT INTO "ConferenceMembership" ("sportTeamId","sportConferenceId","sportId","seasonYear") VALUES (101,500,1,2026),(102,500,1,2026),(103,500,1,2026);\n            INSERT INTO "Week" (id,"leagueId","weekNumber","startDate","endDate","isLocked","scoringComplete") VALUES\n            (100,10,1,\'2026-10-01\',\'2026-10-07\',true,true),(101,10,2,\'2026-10-08\',\'2026-10-14\',true,true),\n            (200,20,1,\'2026-10-01\',\'2026-10-07\',true,true),(300,30,1,\'2026-10-01\',\'2026-10-07\',true,true);\n            INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") VALUES\n            (10,11,101,1,\'Draft\'),(10,12,102,1,\'Draft\'),(20,21,103,1,\'Draft\'),(30,31,201,1,\'Draft\');\n            INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name,rules,"startDate","endDate") VALUES\n            (10,1,\'PrimaryPlayoffs\',\'Primary\',\'{"primaryPostseason":true}\',\'2026-10-01\',\'2026-10-31\'),\n            (20,1,\'SegmentPlayoffs\',\'Segment\',\'{}\',\'2026-10-01\',\'2026-10-31\');\n            INSERT INTO "GameResult" (sport,"externalGameId",date,"homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName","sportSeasonId","seasonPhaseId","roundOrder") VALUES\n            (1,\'depthA\',\'2026-10-03\',101,103,20,10,101,103,\'A\',\'C\',1,10,3),\n            (1,\'depthB\',\'2026-10-04\',102,103,10,20,102,103,\'B\',\'C\',1,10,2),\n            (1,\'primaryH2H\',\'2026-10-05\',101,102,10,20,101,102,\'A\',\'B\',1,10,1),\n            (1,\'segment\',\'2026-10-06\',101,102,10,20,101,102,\'A\',\'B\',1,20,1);\n            INSERT INTO "WeeklyTeamScore" ("leagueId","weekId","memberId","pointsAwarded","pointDifferential",rank) VALUES\n            (10,100,11,2,5,1),(10,100,12,1,-5,2),(10,101,11,2,-5,2),(10,101,12,3,5,1),\n            (20,200,21,1,0,1),(30,300,31,1,0,1);'


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
        query('''UPDATE "ConferenceMembership" SET "seasonYear"=NULL; UPDATE "Week" SET "isLocked"=false,"scoringComplete"=false;
            INSERT INTO "Conference" (id,name) VALUES (2,'Seasonal'),(3,'Other sport');
            INSERT INTO "SportConference" (id,"sportId","conferenceId","maxTeamsPerOwner") VALUES (600,1,2,1),(700,2,3,2);
            INSERT INTO "ConferenceMembership" ("sportTeamId","sportId","sportConferenceId","seasonYear") VALUES (101,1,600,2026),(201,2,700,NULL);
            INSERT INTO "DraftPick" ("leagueId","overallPickNumber","roundNumber","pickInRound","memberId","sportTeamId") VALUES (10,1,1,1,11,101);''')
    def state():return {t:query(f'SELECT * FROM "{t}" ORDER BY id') for t in ('DraftPick','LeagueTeamSlot','Transaction','GameResult')}
    def rejected(call, fragment=None):
        before=state()
        try:call()
        except ValueError as exc:
            if fragment:assert fragment in str(exc),str(exc)
        else:raise AssertionError('Missing configuration accepted')
        assert state()==before,'Rejected command changed history/state'
    reset()
    with engine.begin() as conn:
        roster=RosterRepository().member_teams(conn,10,11,1)
        assert len(roster)==1 and roster[0]['conferenceName']=='Seasonal',roster
        available=RosterRepository().available_teams(conn,10,1,2026,100,1)
        assert len({r['id'] for r in available})==len(available)
        read=ScheduleReadRepository()
        rows=read.search_teams(conn,dict(leagueId=10,seasonYear=2026,sport=1,weekNumber=1)).mappings().all()
        assert len(rows)==3 and next(r for r in rows if r['teamId']==101)['conferenceName']=='Seasonal',rows
        owned=read.owned_teams(conn,dict(leagueId=10,memberId=11,weekNumber=1)).mappings().all()
        assert len(owned)==1 and owned[0]['sportConferenceId']==600,owned
        history=DraftSnapshotRepository().snapshot_picks(conn,10)
        assert len(history)==1 and history[0]['conferenceName']=='Seasonal',history
        confs=LeagueReadRepository().season_conferences(conn,1,2026)
        assert {r['sportConferenceId']:r['teamsInConference'] for r in confs}=={500:2,600:1},confs
        pick=DraftPickRepository()
        assert pick.conference_info(conn,dict(leagueId=10,sportTeamId=101)).fetchone()._mapping['sportConferenceId']==600
        assert pick.member_conference_count(conn,dict(leagueId=10,memberId=11,weekNumber=1,sportConferenceId=600)).scalar_one()==1
        assert pick.owned_conference_count(conn,dict(leagueId=10,memberId=11,week=1,sportConferenceId=500)).scalar_one()==0
        trade=TransactionRepository()
        assert trade.conference_counts(conn,10,1,11,[])=={600:1}
        assert trade.incoming_confs(conn,[101,102],10)=={600:1,500:1}
        workflow=TransactionWorkflowRepository()
        assert workflow.member_conference_counts(conn,dict(league_id=10,member_id=11,week_number=1)).fetchone()._mapping['sportConferenceId']==600
        assert workflow.team_conference_info(conn,dict(league_id=10,team_ids=[101])).fetchone()._mapping['sportConferenceId']==600
        assert not ScheduleIngestionRepository().shared_conferences(conn,dict(season=1,home=101,away=102)).fetchall()
        games=read.conference_games(conn,dict(sportConferenceId=600,seasonYear=2026,leagueId=10,weekNumber=1,weekStart="2026-10-01",weekEnd="2026-10-31")).fetchall()
        assert len(games)==len({r._mapping['id'] for r in games})
    # The same exact-season mapping removes a team from the default conference.
    query('INSERT INTO "ConferenceMembership" ("sportTeamId","sportId","sportConferenceId","seasonYear") VALUES (102,1,600,2026)')
    with engine.begin() as conn:
        assert [r[0] for r in ScheduleIngestionRepository().shared_conferences(conn,dict(season=1,home=101,away=102))]==[600]
    # Missing mappings remain visible to reads, never usable as uncapped teams.
    reset();query('DELETE FROM "ConferenceMembership" WHERE "sportTeamId"=103')
    with engine.begin() as conn:assert DraftPickService(engine)._choose_random_team_for_auto_pick(conn,10,11,1) is None
    rejected(lambda:DraftPickService(engine).allocate_manual_for_job(10,11,103), "Conference")
    rejected(lambda:TransactionWorkflowService(engine).free_agency_for_job(10,100,1,11,103,101), "Conference")
    query('DELETE FROM "ConferenceMembership" WHERE "sportTeamId"=101')
    with engine.begin() as conn:
        assert RosterRepository().member_teams(conn,10,11,1)[0]['conferenceName'] is None
        assert DraftSnapshotRepository().snapshot_picks(conn,10)[0]['conferenceName'] is None
    # Review regressions: retained dirty metadata cannot bypass timeout, and
    # cross-sport historical rows remain visible without foreign conference data.
    reset();query('DELETE FROM "ConferenceMembership" WHERE "sportTeamId"=102')
    query('''UPDATE "League" SET settings=settings || '{"draft":{"draftType":"SNAKE","selectionTime":60,"numberOfRounds":2,"timeoutAction":"AUTO-PICK","graceSeconds":0}}'::jsonb WHERE id=10;
        INSERT INTO "DraftState" ("leagueId",status,"currentOverallPickNumber","currentMemberId","expiresAt") VALUES (10,'live',2,12,'2000-01-01');
        INSERT INTO "DraftTurn" ("leagueId","overallPickNumber","memberId") VALUES (10,1,11),(10,2,12),(10,3,12),(10,4,11);''')
    before_state=query('SELECT * FROM "DraftState"');before_turns=query('SELECT * FROM "DraftTurn" ORDER BY "overallPickNumber"')
    rejected(lambda:DraftPickService(engine).process_timeout_for_job(10),'Conference configuration')
    assert query('SELECT * FROM "DraftState"')==before_state
    assert query('SELECT * FROM "DraftTurn" ORDER BY "overallPickNumber"')==before_turns
    reset();query('''INSERT INTO "LeagueTeamSlot" ("leagueId","memberId","sportTeamId","acquiredWeek","acquiredVia") VALUES (10,11,201,1,'Prior');
        INSERT INTO "DraftPick" ("leagueId","overallPickNumber","roundNumber","pickInRound","memberId","sportTeamId") VALUES (10,2,1,2,11,201);''')
    with engine.begin() as conn:
        projections=[(RosterRepository().member_teams(conn,10,11,1),'sportTeamId'),
            ([dict(r._mapping) for r in ScheduleReadRepository().owned_teams(conn,dict(leagueId=10,memberId=11,weekNumber=1))],'teamId'),
            (DraftSnapshotRepository().snapshot_picks(conn,10),'sportTeamId')]
        for rows,key in projections:
            invalid=next(row for row in rows if row[key]==201)
            assert invalid['conferenceName'] is None and invalid['sportConferenceId'] is None,invalid
    # Actual seasonal cap: current500 permits3 but seasonal600 permits only1.
    reset();query('INSERT INTO "ConferenceMembership" ("sportTeamId","sportId","sportConferenceId","seasonYear") VALUES (103,1,600,2026)')
    rejected(lambda:DraftPickService(engine).allocate_manual_for_job(10,11,103))
    rejected(lambda:TransactionWorkflowService(engine).free_agency_for_job(10,100,1,11,103,None), "maxTeamsPerOwner")
    # Valid mapped independent analogue follows configured conference and cap.
    reset();result=TransactionWorkflowService(engine).free_agency_for_job(10,100,1,11,103,101)
    TransactionWorkflowService(engine).apply_pending_for_job(result['transactionId'])
    assert query('SELECT status FROM "Transaction"')[0]['status']=='COMPLETED'
    reset();query('''INSERT INTO "Transaction" (id,"leagueId","weekId",type,"memberFromId","memberToId",status,"fromTeamIds","toTeamIds") VALUES (1,10,100,'TRADE',11,12,'PENDING_APPLY','[101]','[102]')''')
    query('DELETE FROM "ConferenceMembership" WHERE "sportTeamId"=102')
    rejected(lambda:TransactionWorkflowService(engine).apply_pending_for_job(1))
    # Invalid seasonal reference suppresses valid default; sport mismatches cannot
    # manufacture a fallback cap or allocation.
    reset();query('UPDATE "ConferenceMembership" SET "sportConferenceId"=700 WHERE "sportTeamId"=101 AND "seasonYear"=2026')
    with engine.begin() as conn:assert DraftPickRepository().conference_info(conn,dict(leagueId=10,sportTeamId=101)).fetchone() is None
    rejected(lambda:DraftPickService(engine).allocate_manual_for_job(10,12,201))
    preflight=(ROOT/'db/preflights/20261105_seasonal_consistency.sql').read_text()
    counts=query(preflight)[0];assert counts['invalid_membership_sports']==1 and counts['season_teams_missing_effective_mapping']>0,counts
    reset();query('UPDATE "ConferenceMembership" SET "sportId"=2,"sportConferenceId"=700 WHERE "sportTeamId"=101 AND "seasonYear"=2026')
    with engine.begin() as conn:assert DraftPickRepository().conference_info(conn,dict(leagueId=10,sportTeamId=101)).fetchone() is None
    assert query(preflight)[0]['season_teams_missing_effective_mapping']==1
    reset();assert all(n==0 for n in query(preflight)[0].values()),query(preflight)
    query('''INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name) VALUES (30,2,'RegularSeason','Other');
        UPDATE "GameResult" SET "seasonPhaseId"=30 WHERE id=1;
        INSERT INTO "TournamentDefinition" (id,"sportId",code,name,scope,"sportConferenceId") VALUES (1,2,'synthetic','Wrong sport','conference',600);
        UPDATE "SeasonPhase" SET "tournamentId"=1 WHERE id=10;''')
    counts=query(preflight)[0]
    assert counts['game_phase_season_mismatches']==1 and counts['phase_tournament_sport_mismatches']==1 and counts['tournament_conference_sport_mismatches']==1,counts
    reset()
    params=dict(sport=1,sportSeasonId=1,seasonPhaseId=10,externalGameId='guarded',date='2026-10-03',timeTBD=False,homeTeamId=101,awayTeamId=None,homeScore=0,awayScore=0,homeTeamExternalId='101',awayTeamExternalId='999',homeTeamName='A',awayTeamName='External',broadcast=None)
    def upsert(values):
        with engine.begin() as conn:return ScheduleIngestionRepository().upsert_game(conn,values).scalar_one()
    for changes in (dict(sportSeasonId=2),dict(homeTeamId=201),dict(sport=2,sportSeasonId=2,seasonPhaseId=10,homeTeamId=201)):
        rejected(lambda:upsert({**params,**changes}))
    first=upsert(params);assert upsert({**params,'seasonPhaseId':None})==first
    query('UPDATE "GameResult" SET sport=2 WHERE "externalGameId"=\'guarded\'')
    counts=query(preflight)[0];assert counts['game_season_sport_mismatches']==1 and counts['game_team_sport_mismatches']==1,counts
    return {'effective_read_families':'PASS','seasonal_counts_and_caps':'PASS','unmapped_write_rollback_and_auto_no_pick':'PASS',
            'timeout_retained_mapping_rollback':'PASS','cross_sport_history_nullable_metadata':'PASS','retained_history_nullable_metadata':'PASS','mapped_conference_required':'PASS','ingestion_reference_validation_and_nullable_refs':'PASS',
            'read_only_preflight_clean_dirty':'PASS','schema_constraints':'Proposal only; no migration/rollout'}


def main():
    admin=psycopg2.connect(dbname='postgres',**LOCAL);admin.autocommit=True
    name='otm_mod015_'+uuid4().hex;created=False;engine=None
    try:
        with admin.cursor() as cursor:
            cursor.execute("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")
            assert cursor.fetchone()[0]=='otm-modernization-assessment-20261029-synthetic-only','Refusing unmarked server'
            cursor.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
        engine=engine_for(name,'mod015-owner');result=tests(engine,name)
        result['prior_ownership']=prior_ownership_tests(engine,name)
        result['prior_draft_snapshot']=snapshot_tests(engine,name)
        result['prior_draft_finalization']=finalize_tests(engine,name)
        result['prior_draft_control']=control_tests(engine,name)
        result['prior_draft_order']=order_tests(engine,name)
        result['prior_draft']=prior_draft_tests(engine,name)
        result['prior_transaction']=prior_transaction_tests(engine,name)
        result['prior_calendar']=calendar_tests(engine)
        result['prior_schedule_member']=member_tests(engine)
        result['prior_schedule_views']=view_tests(engine)
        result['prior_schedule']=prior_schedule_tests(engine)
        with engine.begin() as conn:conn.exec_driver_sql('DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
        result['prior_roster']=prior_roster_tests(engine,name)
        files=['api/utils/conference_membership.py']
        files += ['api/endpoints/'+file for file in ('schedule/read_repository.py','schedule/ingestion_repository.py','roster/repository.py','league/reads/repository.py','draft/pick_repository.py','draft/pick_service.py','draft/snapshot_repository.py','transaction/repository.py','transaction/service.py','transaction/workflow_repository.py','transaction/workflow_service.py')]
        files += ['db/preflights/20261105_seasonal_consistency.sql','scripts/modernization/verify_mod015.py','db/baselines/20261029/001_schema.sql','scripts/modernization/verify_draft_snapshot.py','scripts/modernization/verify_draft_finalization.py','scripts/modernization/verify_draft_complete.py','scripts/modernization/verify_transaction_complete.py','scripts/modernization/verify_schedule_member_reads.py','scripts/modernization/verify_schedule_views_search.py','scripts/modernization/verify_schedule_complete.py','scripts/modernization/verify_roster_pilot.py']
        files += ['api/tests/test_seasonal_membership.py','api/tests/test_schedule_time_tbd_persistence.py']
        files += ['api/migrations/'+file for file in ('20261030_game_kickoff_tbd.sql','20261104_user_identity_unique.sql','20261104_week_score_identity.sql','20261104_ownership_integrity.sql')]
        files += ['front-end/src/'+file for file in ('components/League/LeagueDraftHistory.tsx','components/League/LeagueScheduleTabs.tsx','screens/League/LeagueDraftPage.tsx','screens/League/LeagueRosterPage.tsx','screens/League/TeamLookupPage.tsx','utils/draftedTeamGroups.ts','utils/teamTierGroups.ts')]
        files += ['front-end/tests/draftedTeamGroups.test.ts']
        report={'result':'PASS','scope':'Owned marked loopback PostgreSQL only; no configured jobs or leagues','tests':result,
                'sha256':{file:hashlib.sha256((ROOT/file).read_bytes()).hexdigest() for file in files}}
        (ROOT/'docs/modernization/evidence/mod-015-postgres-2026-11-05.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    finally:
        if engine is not None:engine.dispose()
        if created:
            with admin.cursor() as cursor:cursor.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        admin.close()
if __name__=='__main__':main()
