"""Native acceptance for prepared MOD015 DDL; marked disposable localhost only."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path
import psycopg2
from sqlalchemy import create_engine,text
import measure_mod017 as base
from measure_mod017_transactions import verify_cleanup,save_json
from mod017_index_support import snapshot_catalog,catalog_identity
MIGRATION=base.ROOT/'api/migrations/20261117_seasonal_reference_integrity.sql'
FIXTURE='''
INSERT INTO "Sport" (id,name) VALUES (1,'One'),(2,'Two');
INSERT INTO "School" (id,name) VALUES (1,'School');
INSERT INTO "SportTeam" (id,"schoolId","sportId","displayName") VALUES (1,1,1,'One'),(2,1,1,'Two'),(3,1,2,'Other'),(4,1,1,'AwayDelete'),(5,1,1,'HomeDelete');
INSERT INTO "Conference" (id,name) VALUES (1,'One'),(2,'Two');
INSERT INTO "SportConference" (id,"conferenceId","sportId","maxTeamsPerOwner") VALUES (1,1,1,4),(2,2,2,4);
INSERT INTO "SportSeason" (id,"sportId","seasonYear","seasonStart","seasonEnd") VALUES (1,1,2026,'2026-01-01','2026-12-31'),(2,2,2025,'2025-01-01','2025-12-31');
INSERT INTO "SeasonPhase" (id,"sportSeasonId",type,name) VALUES (1,1,'REGULAR','One'),(2,2,'REGULAR','Two');
INSERT INTO "ConferenceMembership" (id,"sportTeamId","sportConferenceId","sportId") VALUES (1,1,1,1),(2,3,2,2);
INSERT INTO "GameResult" (id,sport,"sportSeasonId","seasonPhaseId","externalGameId",date,"homeTeamId","awayTeamId","homeScore","awayScore","homeTeamExternalId","awayTeamExternalId","homeTeamName","awayTeamName") VALUES
(1,1,1,1,'fixture','2026-02-01',1,2,10,7,1,2,'One','Two');
'''
TABLES=['Sport','School','SportTeam','Conference','SportConference','SportSeason','SeasonPhase','ConferenceMembership','GameResult']
DIRTY={
 'null_membership':'UPDATE "ConferenceMembership" SET "sportId"=NULL WHERE id=1',
 'member_team_sport':'UPDATE "ConferenceMembership" SET "sportTeamId"=3 WHERE id=1',
 'member_conference_sport':'UPDATE "ConferenceMembership" SET "sportConferenceId"=2 WHERE id=1',
 'game_season':'UPDATE "GameResult" SET sport=2 WHERE id=1',
 'game_phase':'UPDATE "GameResult" SET "seasonPhaseId"=2 WHERE id=1',
 'game_home':'UPDATE "GameResult" SET "homeTeamId"=3 WHERE id=1',
 'game_away':'UPDATE "GameResult" SET "awayTeamId"=3 WHERE id=1',
 'same_name_drift':'ALTER TABLE "SportTeam" ADD CONSTRAINT "SportTeam_sport_identity_key" UNIQUE (id)',
 'late_name_drift':'ALTER TABLE "GameResult" ADD CONSTRAINT "GameResult_away_sport_fkey" FOREIGN KEY ("awayTeamId") REFERENCES "SportTeam"(id) ON DELETE CASCADE',
 'phase_set_null_drift':'ALTER TABLE "SeasonPhase" ADD CONSTRAINT "SeasonPhase_season_identity_key" UNIQUE (id,"sportSeasonId"); ALTER TABLE "GameResult" ADD CONSTRAINT "GameResult_phase_season_fkey" FOREIGN KEY ("seasonPhaseId","sportSeasonId") REFERENCES "SeasonPhase"(id,"sportSeasonId") ON DELETE SET NULL',
 'legacy_delete_drift':'ALTER TABLE "GameResult" DROP CONSTRAINT "GameResult_homeTeamId_fkey"; ALTER TABLE "GameResult" ADD CONSTRAINT "GameResult_homeTeamId_fkey" FOREIGN KEY ("homeTeamId") REFERENCES "SportTeam"(id) ON DELETE CASCADE',
}

def state(conn):
    return dict(indexes=catalog_identity(snapshot_catalog(conn)),constraints=[tuple(r) for r in conn.exec_driver_sql('''SELECT t.relname,c.conname,pg_get_constraintdef(c.oid),c.convalidated,c.oid FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' ORDER BY t.relname,c.conname''')],columns=[tuple(r) for r in conn.exec_driver_sql('''SELECT t.relname,a.attname,a.attnotnull FROM pg_attribute a JOIN pg_class t ON t.oid=a.attrelid JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' AND a.attnum>0 AND NOT a.attisdropped ORDER BY t.relname,a.attname''')],data={t:base.signature([dict(r) for r in conn.exec_driver_sql('SELECT * FROM public."'+t+'" ORDER BY id').mappings()]) for t in TABLES})

def apply(conn,sql):
    try:conn.execute(text(sql))
    except BaseException:
        conn.exec_driver_sql('ROLLBACK');raise

def direct_controls(conn):
    bad={**{k:v for k,v in DIRTY.items() if 'drift' not in k},
      'parent_team':'UPDATE "SportTeam" SET "sportId"=2 WHERE id=1',
      'parent_conference':'UPDATE "SportConference" SET "sportId"=2 WHERE id=1',
      'parent_season':'UPDATE "SportSeason" SET "sportId"=2 WHERE id=1',
      'parent_phase':'UPDATE "SeasonPhase" SET "sportSeasonId"=2 WHERE id=1'}
    results=[]
    for label,sql in bad.items():
        conn.exec_driver_sql('BEGIN');conn.exec_driver_sql('SAVEPOINT probe')
        try:
            try:conn.execute(text(sql))
            except Exception as error:
                code=getattr(getattr(error,'orig',None),'pgcode',None)
                if code not in ('23502','23503'):raise
                results.append(dict(case=label,sqlstate=code))
            else:raise AssertionError('Invalid direct write accepted: '+label)
        finally:conn.exec_driver_sql('ROLLBACK')
    for label,sql,check in [
      ('nullable_participants','UPDATE "GameResult" SET "homeTeamId"=NULL,"awayTeamId"=NULL,"seasonPhaseId"=NULL WHERE id=1','SELECT count(*) FROM "GameResult" WHERE id=1 AND "homeTeamId" IS NULL AND "awayTeamId" IS NULL AND "seasonPhaseId" IS NULL AND "sportSeasonId"=1'),
      ('phase_delete','DELETE FROM "SeasonPhase" WHERE id=1','SELECT count(*) FROM "GameResult" WHERE id=1 AND "seasonPhaseId" IS NULL AND "sportSeasonId"=1'),
      ('away_delete','UPDATE "GameResult" SET "awayTeamId"=4 WHERE id=1; DELETE FROM "SportTeam" WHERE id=4','SELECT count(*) FROM "GameResult" WHERE id=1'),
      ('season_delete','DELETE FROM "SportSeason" WHERE id=1','SELECT count(*) FROM "GameResult" WHERE id=1')]:
        conn.exec_driver_sql('BEGIN')
        try:
            conn.execute(text(sql));actual=conn.exec_driver_sql(check).scalar_one();expected=0 if label in ('away_delete','season_delete') else 1
            if actual!=expected:raise AssertionError('Delete/null semantics changed: '+label)
            results.append(dict(case=label,expected=expected,observed=actual))
        finally:conn.exec_driver_sql('ROLLBACK')
    conn.exec_driver_sql('BEGIN')
    try:
        conn.exec_driver_sql('UPDATE "GameResult" SET "homeTeamId"=5 WHERE id=1')
        try:conn.exec_driver_sql('DELETE FROM "SportTeam" WHERE id=5')
        except Exception as error:
            if getattr(getattr(error,'orig',None),'pgcode',None)!='23503':raise
            results.append(dict(case='home_delete_no_action',sqlstate='23503'))
        else:raise AssertionError('Home delete unexpectedly cascaded')
    finally:conn.exec_driver_sql('ROLLBACK')
    return results

def run():
    from uuid import uuid4
    artifact=base.ROOT/f'docs/modernization/evidence/mod-015-constraints-2026-11-17-{uuid4().hex}.json'
    report=dict(result='RUNNING',scope='Prepared migration native acceptance only; no configured target',started_at=datetime.now(timezone.utc).isoformat(),databases=[],cases=[])
    save_json(artifact,report);admin=None
    try:
        sql=MIGRATION.read_text();report['migration_sha256']=hashlib.sha256(sql.encode()).hexdigest()
        report['sources']={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in ['scripts/modernization/verify_mod015_constraints.py','scripts/modernization/measure_mod017.py','scripts/modernization/mod017_index_support.py',base.BASELINE,*base.MIGRATIONS]}
        admin=psycopg2.connect(dbname='postgres',**base.LOCAL);admin.autocommit=True
        for label,dirty in [('clean',None),*DIRTY.items()]:
            record=None
            try:
                with base.owned_database(admin) as name:
                    record=dict(name=name,cleanup='pending');report['databases'].append(record)
                    engine=create_engine('postgresql+psycopg2://',creator=lambda:psycopg2.connect(dbname=name,**base.LOCAL))
                    try:
                        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
                            base.schema(conn);conn.execute(text(FIXTURE))
                            if label=='clean':report['settings']={key:conn.exec_driver_sql('SHOW '+key).scalar_one() for key in ['server_version','TimeZone','lock_timeout','statement_timeout']}
                            if dirty:conn.execute(text(dirty))
                            before=state(conn)
                            if dirty:
                                try:apply(conn,sql)
                                except Exception as error:
                                    if 'MOD-015 blocked:' not in str(error):raise
                                else:raise AssertionError('Dirty/drift migration accepted: '+label)
                                if state(conn)!=before:raise AssertionError('Atomic refusal altered catalog/data: '+label)
                                report['cases'].append(dict(case=label,result='REFUSED_ATOMICALLY',catalog_and_rows_preserved=True))
                            else:
                                apply(conn,sql);after=state(conn)
                                if len(after['constraints'])-len(before['constraints'])!=10:raise AssertionError('Expected four parent keys and six composite FKs')
                                if before['data']!=after['data']:raise AssertionError('Upgrade rewrote rows')
                                apply(conn,sql)
                                if state(conn)!=after:raise AssertionError('Replay changed catalog/data')
                                controls=direct_controls(conn)
                                if state(conn)!=after:raise AssertionError('Probe rollback changed state')
                                report['cases'].append(dict(case=label,result='UPGRADE_REPLAY_PASS',rows_preserved=True,direct_controls=controls,new_constraints=len(after['constraints'])-len(before['constraints'])))
                            print('MOD015 '+label+' PASS',flush=True)
                    finally:engine.dispose()
            finally:
                if record:verify_cleanup(admin,record)
        if any(r['cleanup']!='removed' for r in report['databases']):raise AssertionError('Unverified owned cleanup')
        report.update(result='PASS',cleanup='verified',completed_at=datetime.now(timezone.utc).isoformat())
        return report
    except BaseException as error:report.update(result='FAILED',error_type=type(error).__name__);raise
    finally:
        if admin:admin.close()
        save_json(artifact,report)
if __name__=='__main__':run()
