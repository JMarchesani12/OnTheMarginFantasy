"""Free agency: actual JWT/routes/domain SQL against synthetic SQLite.

ANY lists, JSONB casts/expansion and now() are adapted; PostgreSQL locks/RLS
and concurrent revocation are not verified. No app factory/jobs/live DB.
"""
import json
import re
import time
import unittest
import jwt
from flask import Flask
from sqlalchemy import text
from authMiddleware import install_auth_middleware
from endpoints.transaction.routes import setup_routes
from endpoints.transaction.transactionModel import TransactionModel
from test_league_read_authorization import ReadDatabase
from test_profile_regression import ALICE, BOB
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET


class TransactionDatabase(ReadDatabase):
    def __init__(self):
        super().__init__()
        self.queries = []
        self.connection.create_function('now', 0, lambda: '2026-10-29')

    def execute(self, statement, params=None):
        sql = str(statement)
        self.queries.append(sql)
        params = dict(params or {})
        for name in re.findall(r'ANY\(:(\w+)\)', sql):
            values = params.pop(name)
            placeholders = []
            for index, value in enumerate(values):
                key = f'{name}_{index}'
                params[key] = value
                placeholders.append(':' + key)
            sql = sql.replace(f'= ANY(:{name})', 'IN (' + ','.join(placeholders) + ')')
        sql = re.sub(r'CAST\((:\w+) AS jsonb\)', r'\1', sql)
        for column in ('toTeamIds', 'fromTeamIds'):
            sql = sql.replace(f'(jsonb_array_elements_text(t."{column}"))::int',
                              'CAST(j.value AS INTEGER)').replace(
                f'FROM "Transaction" t\n',
                f'FROM "Transaction" t, json_each(t."{column}") j\n',
                1) if f'jsonb_array_elements_text(t."{column}")' in sql else sql
        result = super().execute(text(sql), params)
        class Scalars:
            def all(self):
                return [next(iter(row.values())) for row in result.all()]
        result.scalars = Scalars
        return result


class FreeAgencyAuthorizationTests(unittest.TestCase):
    database_type = TransactionDatabase
    def setUp(self):
        self.db = self.database_type()
        self.addCleanup(self.db.connection.close)
        self.db.connection.executescript('''
            CREATE TABLE League (id INTEGER,commissioner INTEGER,settings TEXT,freeAgentDeadline TEXT);
            INSERT INTO League VALUES (10,1,'{"roster":{"maxSwaps":5}}',NULL),(20,2,'{}',NULL);
            CREATE TABLE LeagueMember (id INTEGER,leagueId INTEGER,userId INTEGER);
            INSERT INTO LeagueMember VALUES (11,10,1),(12,10,2),(21,20,2);
            CREATE TABLE Week (id INTEGER,leagueId INTEGER,weekNumber INTEGER,isLocked BOOLEAN);
            INSERT INTO Week VALUES (100,10,1,false),(101,10,2,false),(200,20,1,false);
            CREATE TABLE LeagueTeamSlot (id INTEGER PRIMARY KEY,leagueId INTEGER,memberId INTEGER,
                sportTeamId INTEGER,acquiredWeek INTEGER,droppedWeek INTEGER,acquiredVia TEXT);
            INSERT INTO LeagueTeamSlot VALUES (1,10,11,101,1,NULL,'Draft'),(2,10,12,102,1,NULL,'Draft'),
                (3,20,21,101,1,NULL,'Draft');
            CREATE TABLE ConferenceMembership (sportTeamId INTEGER,sportConferenceId INTEGER);
            INSERT INTO ConferenceMembership VALUES (101,500),(102,500),(103,500);
            CREATE TABLE SportConference (id INTEGER,maxTeamsPerOwner INTEGER);
            INSERT INTO SportConference VALUES (500,3);
            CREATE TABLE "Transaction" (id INTEGER PRIMARY KEY AUTOINCREMENT,leagueId INTEGER,weekId INTEGER,
                type TEXT,memberFromId INTEGER,memberToId INTEGER,status TEXT,fromTeamIds TEXT,toTeamIds TEXT);
        ''')
        app = Flask(__name__)
        app.config['TESTING'] = True
        install_auth_middleware(app)
        setup_routes(app, self.db)
        self.client = app.test_client()
        self.model = TransactionModel(self.db)
        self.body = dict(weekId=100,weekNumber=99,memberId=11,dropTeamId=101,addTeamId=103)

    def headers(self, subject=ALICE, **overrides):
        claims=dict(sub=subject,aud='authenticated',iss=ISSUER,exp=int(time.time())+600)
        claims.update(overrides)
        token=jwt.encode(claims,SUPABASE_JWT_SECRET,algorithm='HS256')
        return {'Authorization':f'Bearer {token}'}

    def post(self, body=None, league=10, subject=ALICE):
        return self.client.post(f'/api/league/{league}/freeAgency/addDrop',
            json=self.body if body is None else body,headers=self.headers(subject))

    def state(self):
        return {table:[dict(row) for row in self.db.connection.execute(f'SELECT * FROM "{table}" ORDER BY id')]
                for table in ('Transaction','LeagueTeamSlot')}

    def test_owned_move_preserves_pending_transaction_and_response(self):
        before=self.state()['LeagueTeamSlot']
        response=self.post({key:str(value) for key,value in self.body.items()})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json,dict(leagueId=10,weekId=100,weekNumber=1,transactionId=1,
            type='FREE_AGENT',status='PENDING_APPLY',memberId=11,added=103,dropped=101,memberRosterTeamIds=[103]))
        row=self.state()['Transaction'][0]
        self.assertEqual((row['leagueId'],row['memberFromId'],row['memberToId'],row['status']),(10,11,11,'PENDING_APPLY'))
        self.assertEqual(json.loads(row['fromTeamIds']),[101])
        self.assertEqual(json.loads(row['toTeamIds']),[103])
        self.assertEqual(self.state()['LeagueTeamSlot'],before)

    def test_foreign_members_and_wrong_leagues_denied_without_domain_reads(self):
        for subject,league,member in ((ALICE,10,12),(ALICE,20,21),(BOB,10,21),(BOB,20,12),
                                     (ALICE,999,11),(ALICE,10,999)):
            with self.subTest(subject=subject,league=league,member=member):
                before=self.state()
                self.db.queries.clear()
                response=self.post(dict(self.body,memberId=member,weekId=200 if league==20 else 100,
                    dropTeamId=102 if member==12 else 101,trustedJob=True,actingUserId=2),league,subject)
                self.assertEqual(response.status_code,404)
                self.assertEqual(response.json,{'message':'League member not found'})
                self.assertEqual(self.state(),before)
                self.assertFalse(any('FROM "Week"' in sql or 'FROM "Transaction"' in sql for sql in self.db.queries))

    def test_noncommissioner_can_move_own_roster(self):
        response=self.post(dict(self.body,memberId=12,dropTeamId=102),subject=BOB)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['memberId'],12)

    def test_auth_missing_and_ambiguous_identity_denied(self):
        before=self.state()
        for headers,status in (({},401),({'Authorization':'Bearer invalid'},401),
                               (self.headers(exp=1),401),(self.headers('missing'),403)):
            response=self.client.post('/api/league/10/freeAgency/addDrop',json=self.body,headers=headers)
            self.assertEqual(response.status_code,status)
        self.db.connection.executescript('''
            ALTER TABLE "User" RENAME TO old_user;
            CREATE TABLE "User" AS SELECT * FROM old_user;
            INSERT INTO "User" SELECT 3,uuid,'duplicate@example.test','Duplicate',createdAt FROM old_user WHERE id=1;
        ''')
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.state(),before)

    def test_invalid_scalar_inputs_are_rejected_without_mutation(self):
        before=self.state()
        for field in self.body:
            for value in (True,1.5,[],{},'bad'):
                with self.subTest(field=field,value=value):
                    self.assertEqual(self.post(dict(self.body,**{field:value})).status_code,400)
        self.assertEqual(self.post([]).status_code,400)
        self.assertEqual(self.state(),before)

    def test_trusted_calls_remain_independent_of_http(self):
        result=self.model.free_agency_add_drop(20,200,99,21,103,101)
        self.assertEqual((result['leagueId'],result['memberId'],result['status']),(20,21,'PENDING_APPLY'))

    def test_locked_week_and_domain_rejections_are_preserved(self):
        self.db.connection.execute('UPDATE Week SET isLocked=true WHERE id=100')
        response=self.post()
        self.assertEqual(response.status_code,200)
        self.assertEqual((response.json['weekId'],response.json['weekNumber']),(101,2))
        before=self.state()
        self.assertEqual(self.post().status_code,400)  # pending add/drop collision
        self.assertEqual(self.state(),before)

    def test_deadline_swap_limit_and_team_ownership_fail_without_mutation(self):
        for setup in ("UPDATE League SET freeAgentDeadline='2026-01-01' WHERE id=10",
                      "UPDATE League SET settings='{\"roster\":{\"maxSwaps\":1}}' WHERE id=10",
                      'UPDATE LeagueTeamSlot SET memberId=12 WHERE id=1',
                      'UPDATE SportConference SET maxTeamsPerOwner=0'):
            with self.subTest(setup=setup):
                self.db.connection.execute(setup)
                if 'maxSwaps' in setup:
                    self.db.connection.execute('''INSERT INTO "Transaction" (leagueId,memberFromId,type)
                        VALUES (10,11,'FREE_AGENT')''')
                self.db.connection.commit()
                before=self.state()
                self.assertEqual(self.post().status_code,400)
                self.assertEqual(self.state(),before)
                # Restore this subcase's fixture.
                self.db.connection.execute('UPDATE League SET freeAgentDeadline=NULL,settings=\'{}\'')
                self.db.connection.execute('UPDATE LeagueTeamSlot SET memberId=11 WHERE id=1')
                self.db.connection.execute('UPDATE SportConference SET maxTeamsPerOwner=3')
                self.db.connection.execute('DELETE FROM "Transaction"')
                self.db.connection.commit()

    def test_late_owner_change_rolls_back_pending_insert(self):
        before=self.state()
        def revoke(sql):
            if 'INSERT INTO "Transaction"' in sql:
                self.db.before_query=None
                self.db.connection.execute('UPDATE LeagueMember SET userId=2 WHERE id=11')
        self.db.before_query=revoke
        response=self.post()
        self.assertEqual(response.status_code,404)
        self.assertEqual(self.state(),before)
        self.assertEqual(self.db.connection.execute('SELECT userId FROM LeagueMember WHERE id=11').fetchone()[0],1)

    def test_operational_error_does_not_leak_details_or_commit(self):
        before=self.state()
        def fail(sql):
            if 'INSERT INTO "Transaction"' in sql:
                raise RuntimeError('private SQL details')
        self.db.before_query=fail
        response=self.post()
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.json,{'message':'Failed to process free agency move'})
        self.assertEqual(self.state(),before)

    def test_add_only_drop_only_and_null_optional_fields_remain_supported(self):
        for body,added,dropped,roster in (
                (dict(weekId=100,weekNumber=1,memberId=11,addTeamId=103,dropTeamId=None),103,None,[101,103]),
                (dict(weekId=100,weekNumber=1,memberId=11,dropTeamId=101),None,101,[])):
            with self.subTest(body=body):
                response=self.post(body)
                self.assertEqual(response.status_code,200)
                self.assertEqual((response.json['added'],response.json['dropped'],response.json['memberRosterTeamIds']),
                                 (added,dropped,roster))
                self.db.connection.execute('DELETE FROM "Transaction"')
                self.db.connection.commit()
        before=self.state()
        self.assertEqual(self.post(dict(weekId=100,weekNumber=1,memberId=11)).status_code,400)
        self.assertEqual(self.state(),before)

    def test_owned_member_cannot_use_week_from_another_league(self):
        before=self.state()
        self.assertEqual(self.post(dict(self.body,weekId=200)).status_code,400)
        self.assertEqual(self.state(),before)

    def test_ownership_is_rechecked_before_transaction_work(self):
        def revoke(sql):
            if 'SELECT COUNT(*)' in sql and 'FROM "LeagueMember"' in sql:
                self.db.before_query=None
                self.db.connection.execute('UPDATE LeagueMember SET userId=2 WHERE id=11')
        self.db.before_query=revoke
        before=self.state()
        response=self.post()
        self.assertEqual(response.status_code,404)
        self.assertEqual(self.state(),before)
