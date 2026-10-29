"""MOD-003C member roster reads: real JWT/routes/SQL, synthetic SQLite only."""
import time
import unittest
import jwt
from flask import Flask
from authMiddleware import install_auth_middleware
from endpoints.roster.routes import setup_routes
from endpoints.roster.rosterModel import RosterModel
from test_league_read_authorization import ReadDatabase
from test_profile_regression import ALICE, BOB
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET


class RosterReadTests(unittest.TestCase):
    database_type = ReadDatabase
    def setUp(self):
        self.db = self.database_type()
        self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            CREATE TABLE League (id INTEGER, commissioner INTEGER, seasonYear INTEGER);
            INSERT INTO League VALUES (10,1,2026),(20,2,2026),(30,1,2026);
            CREATE TABLE LeagueMember (id INTEGER, leagueId INTEGER, userId INTEGER);
            INSERT INTO LeagueMember VALUES (11,10,1),(12,10,2),(21,20,2),(31,30,2);
            CREATE TABLE Week (id INTEGER, leagueId INTEGER, weekNumber INTEGER, isLocked BOOLEAN);
            CREATE TABLE LeagueTeamSlot (id INTEGER, leagueId INTEGER, memberId INTEGER,
                sportTeamId INTEGER, acquiredWeek INTEGER, droppedWeek INTEGER, acquiredVia TEXT);
            INSERT INTO LeagueTeamSlot VALUES (1,10,12,101,1,NULL,'draft'),(2,20,21,101,1,NULL,'draft');
            CREATE TABLE SportTeam (id INTEGER, displayName TEXT, tier INTEGER, sportId INTEGER, externalId TEXT);
            INSERT INTO SportTeam VALUES (101,'Synthetic Team',1,1,'test');
            CREATE TABLE ConferenceMembership (sportTeamId INTEGER,sportId INTEGER,seasonYear INTEGER,sportConferenceId INTEGER);
            CREATE TABLE SportConference (id INTEGER,sportId INTEGER,conferenceId INTEGER);
            CREATE TABLE Conference (id INTEGER,name TEXT);
        ''')
        app = Flask(__name__)
        app.config['TESTING'] = True
        install_auth_middleware(app)
        setup_routes(app, self.db)
        self.client = app.test_client()

    def read(self, league=10, member=12, subject=ALICE, **extra):
        token = jwt.encode(dict(sub=subject,aud='authenticated',iss=ISSUER,exp=int(time.time())+600),
                           SUPABASE_JWT_SECRET,algorithm='HS256')
        return self.client.post('/api/roster/memberTeams',headers={'Authorization':f'Bearer {token}'},
            json=dict(leagueId=league,memberId=member,weekNumber=1,**extra))

    def test_same_league_other_member_reads_remain_allowed(self):
        for subject in (ALICE, BOB):
            response = self.read(subject=subject)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json[0]['sportTeamId'],101)

    def test_commissioner_without_membership_can_read(self):
        self.assertEqual(self.read(30,31).status_code,200)

    def test_cross_user_cross_league_and_missing_resources_denied(self):
        for league, member in ((20,21),(10,21),(20,12),(999,12),(10,999)):
            with self.subTest(league=league,member=member):
                response = self.read(league,member,actingUserId=2,trustedJob=True)
                self.assertEqual(response.status_code,404)
                self.assertEqual(response.json,{'message':'League member not found'})

    def test_auth_and_missing_profile_denied(self):
        self.assertEqual(self.client.post('/api/roster/memberTeams',json={}).status_code,401)
        self.assertEqual(self.read(subject='missing').status_code,403)

    def test_malformed_inputs_are_400(self):
        for member in (True, [], 'bad', None):
            self.assertEqual(self.read(member=member).status_code,400)

    def test_trusted_model_access_remains_explicitly_context_free(self):
        rows = RosterModel(self.db).get_member_teams_for_week(20,21,1)
        self.assertEqual(rows[0]['slotId'],2)

    def test_revocation_before_roster_query_does_not_expose_rows(self):
        def revoke(sql):
            if 'WITH league_info' in sql:
                self.db.before_query = None
                self.db.connection.execute('DELETE FROM LeagueMember WHERE id=12')
        self.db.before_query = revoke
        response = self.read(subject=BOB)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json,[])

    def test_denial_occurs_before_week_or_roster_reads(self):
        queries = []
        self.db.before_query = queries.append
        self.assertEqual(self.read(20,21).status_code,404)
        self.assertFalse(any('FROM "Week"' in sql or 'WITH league_info' in sql for sql in queries))

    def test_database_errors_have_safe_response(self):
        def fail(sql):
            if 'WITH league_info' in sql:
                raise RuntimeError('private synthetic details')
        self.db.before_query = fail
        response = self.read()
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.json,{'message':'Failed to read member roster'})
