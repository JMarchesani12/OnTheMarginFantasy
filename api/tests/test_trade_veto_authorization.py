"""Veto ownership/scope: real SQL/JWT with existing synthetic transaction fixture."""
import unittest
import test_trade_action_authorization as actions
import test_free_agency_authorization as fixture


class TradeVetoAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=actions.TradeActionAuthorizationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db,self.client,self.model=self.fixture.db,self.fixture.client,self.fixture.model
        self.headers=self.fixture.headers
        self.db.connection.executescript('''
            UPDATE League SET settings='{"transactions":{"tradeVeto":{"enabled":true,"requiredVetoCount":2}}}';
            INSERT INTO "User" (id,uuid) VALUES (4,'voter-four');
            INSERT INTO LeagueMember VALUES (14,10,4),(23,20,3);
            CREATE TABLE TransactionVote (transactionId INTEGER,leagueMemberId INTEGER,veto BOOLEAN,
                PRIMARY KEY(transactionId,leagueMemberId));
        ''')

    def state(self):
        state=self.fixture.state()
        state['TransactionVote']=[dict(row) for row in self.db.connection.execute(
            'SELECT * FROM TransactionVote ORDER BY transactionId,leagueMemberId')]
        return state

    def post(self, member=13, subject='outsider', league=10, tx=1, **extra):
        return self.client.post(f'/api/league/{league}/transaction/{tx}/trade/veto',
            json=dict(memberId=member,**extra),headers=self.headers(subject))

    def test_legitimate_vote_toggle_and_threshold_preserve_contract(self):
        before=self.state()['LeagueTeamSlot']
        for expected_vote,expected_count in ((True,1),(False,0),(True,1)):
            response=self.post(member='13')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json,dict(transactionId=1,status='PROPOSED',memberVetoed=expected_vote,
                                               vetoCount=expected_count,requiredVetoCount=2))
            self.assertEqual(bool(self.state()['TransactionVote'][0]['veto']),expected_vote)
        response=self.post(14,'voter-four')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json,dict(transactionId=1,status='VETOED',memberVetoed=True,vetoCount=2,requiredVetoCount=2))
        self.assertEqual(self.state()['Transaction'][0]['status'],'VETOED')
        self.assertEqual(self.state()['Transaction'][1]['status'],'PROPOSED')
        self.assertEqual(self.state()['LeagueTeamSlot'],before)

    def test_other_league_vote_is_isolated(self):
        response=self.post(23,'outsider',20,2)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['transactionId'],2)
        self.assertEqual(self.state()['TransactionVote'],[dict(transactionId=2,leagueMemberId=23,veto=1)])

    def test_foreign_voter_wrong_url_missing_resources_and_spoofed_jobs_denied(self):
        cases=((13,fixture.ALICE,10,1),(14,'outsider',10,1),(23,'outsider',10,1),
               (13,'outsider',20,1),(23,'outsider',20,1),(13,'outsider',10,2),
               (13,'outsider',10,999),(999,'outsider',10,1),(13,'outsider',999,1))
        for member,subject,league,tx in cases:
            with self.subTest(member=member,subject=subject,league=league,tx=tx):
                before=self.state()
                self.db.queries.clear()
                response=self.post(member,subject,league,tx,trustedJob=True,actingUserId=3,userId=3,leagueId=10)
                self.assertEqual(response.status_code,404)
                self.assertEqual(response.json,{'message':'Trade not found'})
                self.assertEqual(self.state(),before)
                self.assertFalse(any('TransactionVote' in sql for sql in self.db.queries))

    def test_participants_cannot_vote_even_when_commissioner(self):
        for member,subject in ((11,fixture.ALICE),(12,fixture.BOB)):
            before=self.state()
            self.assertEqual(self.post(member,subject).status_code,404)
            self.assertEqual(self.state(),before)

    def test_status_type_and_settings_rules_preserved(self):
        cases=[("UPDATE \"Transaction\" SET status='"+status+"' WHERE id=1")
               for status in ('COMPLETED','REJECTED','CANCELLED','VETOED')]
        cases+= ["UPDATE \"Transaction\" SET type='FREE_AGENT' WHERE id=1",
                 "UPDATE League SET settings='{}' WHERE id=10",
                 "UPDATE League SET settings='{\"transactions\":{\"tradeVeto\":{\"enabled\":true,\"requiredVetoCount\":0}}}' WHERE id=10"]
        for setup in cases:
            with self.subTest(setup=setup):
                self.db.connection.execute(setup)
                self.db.connection.commit()
                before=self.state()
                self.assertEqual(self.post().status_code,400)
                self.assertEqual(self.state(),before)
                self.db.connection.execute("UPDATE \"Transaction\" SET status='PROPOSED',type='TRADE' WHERE id=1")
                self.db.connection.execute('''UPDATE League SET settings=
                    '{"transactions":{"tradeVeto":{"enabled":true,"requiredVetoCount":2}}}' ''')
                self.db.connection.commit()
        self.db.connection.execute("UPDATE \"Transaction\" SET status='PENDING_APPLY' WHERE id=1")
        response=self.post()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['status'],'PENDING_APPLY')

    def test_auth_and_missing_ambiguous_profiles_denied(self):
        before=self.state()
        for headers,status in (({},401),({'Authorization':'Bearer invalid'},401),
                               (self.headers(exp=1),401),(self.headers('missing'),403)):
            response=self.client.post('/api/league/10/transaction/1/trade/veto',json={'memberId':13},headers=headers)
            self.assertEqual(response.status_code,status)
        self.db.connection.executescript('''
            ALTER TABLE "User" RENAME TO old_user;
            CREATE TABLE "User" AS SELECT * FROM old_user;
            INSERT INTO "User" SELECT 5,uuid,'duplicate@example.test','Duplicate',createdAt FROM old_user WHERE id=3;
        ''')
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.state(),before)

    def test_malformed_inputs_fail_without_votes(self):
        before=self.state()
        for member in (True,1.5,[],{},None,'bad'):
            self.assertEqual(self.post(member).status_code,400)
        for body in (None,[],{}):
            response=self.client.post('/api/league/10/transaction/1/trade/veto',json=body,headers=self.headers('outsider'))
            self.assertEqual(response.status_code,400)
        self.assertEqual(self.state(),before)

    def test_late_owner_league_or_participant_change_rolls_back_vote_and_threshold(self):
        for mutation in ('UPDATE LeagueMember SET userId=99 WHERE id=13',
                         'UPDATE "Transaction" SET leagueId=20 WHERE id=1',
                         'UPDATE "Transaction" SET memberFromId=13 WHERE id=1'):
            with self.subTest(mutation=mutation):
                self.db.connection.execute('''UPDATE League SET settings=
                    '{"transactions":{"tradeVeto":{"enabled":true,"requiredVetoCount":1}}}' ''')
                self.db.connection.commit()
                before=self.state()
                def revoke(sql):
                    if 'INSERT INTO "TransactionVote"' in sql:
                        self.db.before_query=None
                        self.db.connection.execute(mutation)
                self.db.before_query=revoke
                self.assertEqual(self.post().status_code,404)
                self.assertEqual(self.state(),before)
                self.assertEqual(self.db.connection.execute('SELECT userId FROM LeagueMember WHERE id=13').fetchone()[0],3)

    def test_trusted_calls_keep_voter_rules_and_no_http_context(self):
        result=self.model.veto_trade(2,23)
        self.assertEqual((result['transactionId'],result['memberVetoed']),(2,True))
        with self.assertRaises(ValueError):
            self.model.veto_trade(1,11)
        with self.assertRaises(ValueError):
            self.model.veto_trade(1,23)

    def test_partial_actor_context_cannot_be_trusted(self):
        for context in ({'league_id':10},{'acting_user_id':3}):
            with self.assertRaises(ValueError):
                self.model.veto_trade(1,13,**context)

    def test_operational_failure_is_safe_and_rolls_back(self):
        before=self.state()
        def fail(sql):
            if 'INSERT INTO "TransactionVote"' in sql:
                raise RuntimeError('private SQL details')
        self.db.before_query=fail
        response=self.post()
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.json,{'message':'Failed to veto trade'})
        self.assertEqual(self.state(),before)
