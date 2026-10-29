"""Final MOD-003C HTTP read/write boundary; synthetic SQL/JWT only."""
import os
import unittest
from unittest.mock import patch
from sqlalchemy import text
from flask import Flask
from authMiddleware import install_auth_middleware
from endpoints.scoring.routes import setup_routes
from endpoints.scoring.scoringModel import ScoringModel
from endpoints.transaction.transactionModel import TransactionModel
import test_free_agency_authorization as fixture


class ScoringDatabase(fixture.TransactionDatabase):
    def execute(self, statement, params=None):
        sql=str(statement)
        params=dict(params or {})
        if '__[POSTCOMPILE_weekNumbers]' in sql:
            values=params.pop('weekNumbers')
            keys=[]
            for i,value in enumerate(values):
                key=f'week_{i}'
                params[key]=value
                keys.append(':'+key)
            sql=sql.replace('__[POSTCOMPILE_weekNumbers]',','.join(keys))
        return super().execute(text(sql),params)


class ScoringAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.FreeAgencyAuthorizationTests()
        self.fixture.database_type=ScoringDatabase
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db,self.headers=self.fixture.db,self.fixture.headers
        self.db.connection.executescript('''
            ALTER TABLE League ADD COLUMN isDiscoverable BOOLEAN DEFAULT true;
            INSERT INTO League VALUES (30,1,'{}',NULL,true);
            ALTER TABLE LeagueMember ADD COLUMN teamName TEXT DEFAULT 'Synthetic';
            INSERT INTO "User" (id,uuid) VALUES (3,'nonmember');
            ALTER TABLE Week ADD COLUMN startDate TEXT DEFAULT '2026-10-01';
            ALTER TABLE Week ADD COLUMN endDate TEXT DEFAULT '2026-10-07';
            CREATE TABLE WeeklyTeamScore (leagueId INTEGER,weekId INTEGER,memberId INTEGER,
                pointsAwarded INTEGER,pointDifferential INTEGER,rank INTEGER);
            INSERT INTO WeeklyTeamScore VALUES (10,100,11,2,10,1),(10,100,12,1,5,2),(20,200,21,8,99,1);
        ''')
        app=Flask(__name__)
        app.config['TESTING']=True
        install_auth_middleware(app)
        with patch.dict(os.environ,{'ESPN_BASE_URL':'https://provider.example.test'}):
            setup_routes(app,self.db)
        self.client=app.test_client()
        self.model=ScoringModel(self.db,None)

    def read(self,kind='points',league=10,subject=fixture.ALICE,body=None):
        if kind=='points':
            return self.client.post(f'/api/league/{league}/pointsAwarded',headers=self.headers(subject),
                json={'weekNumbers':[1]} if body is None else body)
        return self.client.get(f'/api/league/{league}/scoreSeason',headers=self.headers(subject))

    def test_member_and_commissioner_reads_preserve_results(self):
        for subject in (fixture.ALICE,fixture.BOB):
            points=self.read(subject=subject)
            self.assertEqual(points.status_code,200)
            self.assertEqual(points.json['weekNumbers'],[1])
            self.assertEqual([row['memberId'] for row in points.json['results']],[11,12])
            self.assertEqual(points.json['results'][0],dict(weekNumber=1,startDate='2026-10-01',endDate='2026-10-07',
                memberId=11,teamName='Synthetic',pointsAwarded=2,pointDifferential=10,rank=1))
            season=self.read('season',subject=subject)
            self.assertEqual(season.status_code,200)
            self.assertEqual(season.json,dict(leagueId=10,members=[
                dict(memberId=11,teamName='Synthetic',weeklyPoints=2.0,bonusPoints=0.0,totalPoints=2.0),
                dict(memberId=12,teamName='Synthetic',weeklyPoints=1.0,bonusPoints=0.0,totalPoints=1.0)]))
        self.assertEqual(self.read('season',20,fixture.BOB).json['members'][0]['memberId'],21)
        self.assertEqual(self.read('season',30).json,{'leagueId':30,'members':[]})
        self.assertEqual(self.read(league=30).json['results'],[])

    def test_nonmember_cross_league_and_spoofed_actors_denied_before_score_queries(self):
        for kind in ('points','season'):
            for league,subject in ((10,'nonmember'),(20,fixture.ALICE),(30,fixture.BOB),(999,fixture.ALICE)):
                with self.subTest(kind=kind,league=league,subject=subject):
                    self.db.queries.clear()
                    response=self.read(kind,league,subject,{'weekNumbers':[1],'trustedJob':True,'userId':2})
                    self.assertEqual(response.status_code,404)
                    self.assertFalse(any('WeeklyTeamScore' in sql for sql in self.db.queries))

    def test_auth_missing_and_ambiguous_profiles_are_denied(self):
        for path,method in (('/api/league/10/pointsAwarded','post'),('/api/league/10/scoreSeason','get')):
            for headers,status in (({},401),({'Authorization':'Bearer invalid'},401),
                                   (self.headers(exp=1),401),(self.headers('missing'),403)):
                response=getattr(self.client,method)(path,headers=headers,json={'weekNumbers':[1]})
                self.assertEqual(response.status_code,status)
        self.db.connection.executescript('''
            ALTER TABLE "User" RENAME TO old_user;
            CREATE TABLE "User" AS SELECT * FROM old_user;
            INSERT INTO "User" SELECT 4,uuid,'duplicate@example.test','Duplicate',createdAt FROM old_user WHERE id=1;
        ''')
        self.assertEqual(self.read().status_code,403)
        self.assertEqual(self.read('season').status_code,403)

    def test_input_validation_and_integer_string_compatibility(self):
        for body in ([],{}, {'weekNumbers':[]},{'weekNumbers':[True]},{'weekNumbers':[1.5]},
                     {'weekNumbers':['bad']},{'weekNumbers':'1'}):
            self.assertEqual(self.read(body=body).status_code,400)
        response=self.read(body={'weekNumbers':['1',1]})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json['results']),2)

    def test_revocation_during_reads_returns_no_private_scores(self):
        for kind in ('points','season'):
            def revoke(sql):
                if 'WeeklyTeamScore' in sql:
                    self.db.before_query=None
                    self.db.connection.execute('DELETE FROM LeagueMember WHERE id=12')
            self.db.before_query=revoke
            response=self.read(kind,subject=fixture.BOB)
            self.assertEqual(response.status_code,404)
            self.assertEqual(response.json,{'message':'League not found'})
            self.db.connection.execute("INSERT INTO LeagueMember VALUES (12,10,2,'Synthetic')")
            self.db.connection.commit()

    def test_trusted_reads_remain_context_free(self):
        self.assertEqual(self.model.compute_end_of_year_season_standings(20)['members'][0]['memberId'],21)
        self.assertEqual(self.model.get_weekly_points_awarded_for_league(20,[1])[0]['pointsAwarded'],8)

    def test_operational_errors_have_safe_responses(self):
        def fail(sql):
            if 'WeeklyTeamScore' in sql:
                raise RuntimeError('private SQL details')
        self.db.before_query=fail
        for kind in ('points','season'):
            response=self.read(kind)
            self.assertEqual(response.status_code,500)
            self.assertNotIn('private SQL details',str(response.json))


class DisabledOperationalHttpTests(unittest.TestCase):
    def setUp(self):
        self.fixture=ScoringAuthorizationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.score_client=self.fixture.client
        self.trade_client=self.fixture.fixture.client
        self.headers=self.fixture.headers
        self.score=self.enterContext(patch.object(ScoringModel,'compute_weekly_scores'))
        self.apply=self.enterContext(patch.object(TransactionModel,'apply_trade'))
        self.database=self.enterContext(patch.object(self.fixture.db,'begin',side_effect=AssertionError('No HTTP persistence')))
        self.connect=self.enterContext(patch.object(self.fixture.db,'connect',side_effect=AssertionError('No HTTP persistence')))

    def test_http_triggers_are_disabled_for_all_authenticated_actors_and_bodies(self):
        for client,path,error in ((self.score_client,'/api/league/10/scoreWeek/1','http_weekly_scoring_disabled'),
                                  (self.trade_client,'/api/league/10/transaction/1/trade/apply','http_trade_application_disabled')):
            for subject in (fixture.ALICE,fixture.BOB,'nonmember','missing'):
                for body in ({},[],{'trustedJob':True,'actingUserId':1,'userId':1}):
                    response=client.post(path,headers=self.headers(subject),json=body)
                    self.assertEqual(response.status_code,410)
                    self.assertEqual(response.json,{'error':error})
            response=client.post(path,headers=self.headers(),data='{broken',content_type='application/json')
            self.assertEqual(response.status_code,410)
        self.score.assert_not_called()
        self.apply.assert_not_called()
        self.database.assert_not_called()
        self.connect.assert_not_called()

    def test_authentication_still_rejects_anonymous_invalid_and_expired_tokens(self):
        for client,path in ((self.score_client,'/api/league/10/scoreWeek/1'),
                            (self.trade_client,'/api/league/10/transaction/1/trade/apply')):
            for headers in ({},{'Authorization':'Bearer invalid'},self.headers(exp=1)):
                self.assertEqual(client.post(path,headers=headers,json={}).status_code,401)
        self.score.assert_not_called()
        self.apply.assert_not_called()
