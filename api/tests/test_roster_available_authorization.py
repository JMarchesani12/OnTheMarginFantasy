"""Real available-team SQL; only PostgreSQL JSON expansion is adapted to SQLite.

json_each replaces jsonb_array_elements_text + ::int. No deployed PostgreSQL,
RLS or locking behavior is established by this synthetic fixture.
"""
import time
import unittest
import jwt
from sqlalchemy import text
from endpoints.roster.rosterModel import RosterModel
import test_roster_read_authorization as member_roster_tests
from test_league_read_authorization import ReadDatabase
from test_profile_regression import ALICE, BOB
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET


class AvailableDatabase(ReadDatabase):
    def execute(self, statement, params):
        sql = str(statement)
        for column in ('toTeamIds', 'fromTeamIds'):
            sql = sql.replace(
                f'SELECT DISTINCT (jsonb_array_elements_text(t."{column}"))::int AS team_id\n              FROM "Transaction" t',
                f'SELECT DISTINCT CAST(j.value AS INTEGER) AS team_id\n              FROM "Transaction" t, json_each(t."{column}") j')
        return super().execute(text(sql), params)


class AvailableAuthorizationTests(unittest.TestCase):
    database_type = AvailableDatabase

    def setUp(self):
        member_roster_tests.RosterReadTests.setUp(self)
        self.db.connection.executescript('''
            ALTER TABLE League ADD COLUMN sport INTEGER DEFAULT 1;
            ALTER TABLE League ADD COLUMN isDiscoverable BOOLEAN DEFAULT true;
            ALTER TABLE SportTeam ADD COLUMN schoolId INTEGER DEFAULT 1;
            INSERT INTO SportTeam VALUES (102,'Available',1,1,'free',2),
                (103,'Reserved',1,1,'reserved',3),(104,'Other sport',1,2,'other',4);
            INSERT INTO Week VALUES (100,10,1,true),(101,10,2,false),(200,20,1,false),(300,30,1,false);
            CREATE TABLE "Transaction" (leagueId INTEGER,weekId INTEGER,status TEXT,type TEXT,
                toTeamIds TEXT,fromTeamIds TEXT);
            INSERT INTO "Transaction" VALUES
                (10,101,'PENDING_APPLY','FREE_AGENT','[103]','[101]'),
                (20,200,'PENDING_APPLY','FREE_AGENT','[102]',NULL);
        ''')

    def read(self, league=10, subject=ALICE, week=1, **extra):
        token = jwt.encode(dict(sub=subject,aud='authenticated',iss=ISSUER,exp=int(time.time())+600),
                           SUPABASE_JWT_SECRET,algorithm='HS256')
        return self.client.post('/api/roster/availableTeams',headers={'Authorization':f'Bearer {token}'},
            json=dict(leagueId=league,weekNumber=week,**extra))

    def test_member_reads_preserve_pending_filters_sport_and_locked_week_forwarding(self):
        for subject in (ALICE,BOB):
            response = self.read(subject=subject)
            self.assertEqual(response.status_code,200)
            self.assertEqual({row['id'] for row in response.json},{101,102})
            self.assertEqual(set(response.json[0]),{'id','displayName','tier','externalId',
                'schoolId','sportId','sportConferenceId','conferenceId','conferenceName'})
        self.assertEqual({row['id'] for row in self.read(20,BOB).json},{103})

    def test_commissioner_without_membership_allowed(self):
        self.assertEqual(self.read(30).status_code,200)

    def test_nonmembers_discoverability_and_spoofed_job_do_not_grant_access(self):
        self.db.connection.execute('INSERT INTO "User" (id,uuid) VALUES (3,\'outsider\')')
        for league,subject in ((20,ALICE),(10,'outsider'),(30,'outsider'),(999,ALICE)):
            with self.subTest(league=league,subject=subject):
                response = self.read(league,subject,actingUserId=2,memberId=21,trustedJob=True)
                self.assertEqual(response.status_code,404)
                self.assertEqual(response.json,{'message':'League not found'})

    def test_denial_precedes_week_and_available_reads(self):
        queries=[]
        self.db.before_query=queries.append
        self.assertEqual(self.read(20).status_code,404)
        self.assertFalse(any('FROM "Week"' in sql or 'WITH pending_adds' in sql for sql in queries))

    def test_revocation_before_final_query_returns_no_rows(self):
        def revoke(sql):
            if 'WITH pending_adds' in sql:
                self.db.before_query=None
                self.db.connection.execute('DELETE FROM LeagueMember WHERE id=12')
        self.db.before_query=revoke
        response=self.read(subject=BOB)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json,[])

    def test_trusted_model_calls_remain_context_free(self):
        rows=RosterModel(self.db).get_available_teams_for_week(20,1)
        self.assertEqual([row['id'] for row in rows],[103])
        self.assertEqual(RosterModel(self.db).get_available_teams_for_week(999,1),[])

    def test_invalid_integer_inputs_and_json_are_400(self):
        for value in (True,[],{},None,1.5,'bad'):
            for field in ('league','week'):
                with self.subTest(field=field,value=value):
                    self.assertEqual(self.read(**{field:value}).status_code,400)
        for body in ([],None,'invalid'):
            token=jwt.encode(dict(sub=ALICE,aud='authenticated',iss=ISSUER,exp=int(time.time())+600),
                             SUPABASE_JWT_SECRET,algorithm='HS256')
            response=self.client.post('/api/roster/availableTeams',json=body,
                headers={'Authorization':f'Bearer {token}'})
            self.assertEqual(response.status_code,400)
        self.assertEqual(self.read(league='10',week='1').status_code,200)

    def test_missing_profile_and_auth_denied(self):
        self.assertEqual(self.read(subject='missing').status_code,403)
        self.assertEqual(self.client.post('/api/roster/availableTeams',json={}).status_code,401)

    def test_database_failures_have_safe_response(self):
        def fail(sql):
            if 'WITH pending_adds' in sql:
                raise RuntimeError('synthetic private details')
        self.db.before_query=fail
        response=self.read()
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.json,{'message':'Failed to read available teams'})
