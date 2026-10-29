"""Proposal authorization using the existing isolated transaction SQL fixture."""
import json
import unittest
import test_free_agency_authorization as fixture


class TradeProposalAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.FreeAgencyAuthorizationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db, self.client, self.model = self.fixture.db, self.fixture.client, self.fixture.model
        self.headers, self.state = self.fixture.headers, self.fixture.state
        self.db.connection.executescript('''
            ALTER TABLE League ADD COLUMN tradeDeadline TEXT;
            INSERT INTO LeagueMember VALUES (22,20,1);
            INSERT INTO LeagueTeamSlot VALUES (4,20,22,102,1,NULL,'Draft');
        ''')
        self.body = dict(fromMemberId=11,toMemberId=12,fromTeamIds=[101],toTeamIds=[102])

    def post(self, body=None, league=10, week=100, subject=fixture.ALICE):
        return self.client.post(f'/api/league/{league}/week/{week}/trade/propose',
            json=self.body if body is None else body,headers=self.headers(subject))

    def test_owned_proposals_preserve_proposed_transaction_and_response(self):
        before=self.state()['LeagueTeamSlot']
        response=self.post(dict(fromMemberId='11',toMemberId='12',fromTeamIds=['101'],toTeamIds=['102']))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json,{'transactionId':1,'status':'PROPOSED'})
        tx=self.state()['Transaction'][0]
        self.assertEqual((tx['leagueId'],tx['weekId'],tx['memberFromId'],tx['memberToId'],tx['type'],tx['status']),
                         (10,100,11,12,'TRADE','PROPOSED'))
        self.assertEqual(json.loads(tx['fromTeamIds']),[101])
        self.assertEqual(json.loads(tx['toTeamIds']),[102])
        self.assertEqual(self.state()['LeagueTeamSlot'],before)

    def test_noncommissioner_can_propose_own_trade(self):
        response=self.post(dict(fromMemberId=12,toMemberId=11,fromTeamIds=[102],toTeamIds=[101]),subject=fixture.BOB)
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.state()['Transaction'][0]['memberFromId'],12)

    def test_foreign_proposer_cross_league_and_spoofed_actors_denied_before_domain_reads(self):
        cases=((fixture.BOB,10,100,11,12),(fixture.ALICE,10,100,12,11),
               (fixture.ALICE,20,200,21,22),(fixture.BOB,10,100,21,11),
               (fixture.ALICE,999,100,11,12),(fixture.ALICE,10,100,999,12))
        for subject,league,week,proposer,target in cases:
            with self.subTest(subject=subject,league=league,proposer=proposer):
                self.db.queries.clear()
                before=self.state()
                body=dict(self.body,fromMemberId=proposer,toMemberId=target,trustedJob=True,actingUserId=1,
                          userId=1,sub=fixture.ALICE,leagueId=10)
                if proposer==12:
                    body.update(fromTeamIds=[102],toTeamIds=[101])
                response=self.post(body,league,week,subject)
                self.assertEqual(response.status_code,404)
                self.assertEqual(response.json,{'message':'League member not found'})
                self.assertEqual(self.state(),before)
                self.assertFalse(any('FROM "Week"' in sql or 'FROM "LeagueTeamSlot"' in sql for sql in self.db.queries))

    def test_wrong_target_week_and_team_ownership_keep_domain_rejections(self):
        for body,week in ((dict(self.body,toMemberId=21),100),(self.body,200),
                          (dict(self.body,fromTeamIds=[102]),100),(dict(self.body,toTeamIds=[103]),100)):
            with self.subTest(body=body,week=week):
                before=self.state()
                self.assertEqual(self.post(body,week=week).status_code,400)
                self.assertEqual(self.state(),before)

    def test_invalid_json_scalar_and_array_inputs_are_400(self):
        before=self.state()
        for field in ('fromMemberId','toMemberId'):
            for value in (True,1.5,[],{},None,'bad'):
                with self.subTest(field=field,value=value):
                    self.assertEqual(self.post(dict(self.body,**{field:value})).status_code,400)
        for field in ('fromTeamIds','toTeamIds'):
            for value in (None,101,'101',{},[True],[1.5],[{}],['bad']):
                with self.subTest(field=field,value=value):
                    self.assertEqual(self.post(dict(self.body,**{field:value})).status_code,400)
        self.assertEqual(self.post([]).status_code,400)
        self.assertEqual(self.post({}).status_code,400)
        self.assertEqual(self.state(),before)

    def test_auth_missing_and_ambiguous_profiles_fail_without_mutation(self):
        before=self.state()
        for headers,status in (({},401),({'Authorization':'Bearer invalid'},401),
                               (self.headers(exp=1),401),(self.headers('missing'),403)):
            response=self.client.post('/api/league/10/week/100/trade/propose',json=self.body,headers=headers)
            self.assertEqual(response.status_code,status)
        self.db.connection.executescript('''
            ALTER TABLE "User" RENAME TO old_user;
            CREATE TABLE "User" AS SELECT * FROM old_user;
            INSERT INTO "User" SELECT 3,uuid,'duplicate@example.test','Duplicate',createdAt FROM old_user WHERE id=1;
        ''')
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.state(),before)

    def test_late_owner_loss_rolls_back_proposal(self):
        before=self.state()
        def revoke(sql):
            if 'INSERT INTO "Transaction"' in sql:
                self.db.before_query=None
                self.db.connection.execute('UPDATE LeagueMember SET userId=2 WHERE id=11')
        self.db.before_query=revoke
        self.assertEqual(self.post().status_code,404)
        self.assertEqual(self.state(),before)
        self.assertEqual(self.db.connection.execute('SELECT userId FROM LeagueMember WHERE id=11').fetchone()[0],1)

    def test_transaction_entry_rechecks_ownership(self):
        def revoke(sql):
            if 'SELECT COUNT(*)' in sql and 'FROM "LeagueMember"' in sql:
                self.db.before_query=None
                self.db.connection.execute('UPDATE LeagueMember SET userId=2 WHERE id=11')
        self.db.before_query=revoke
        before=self.state()
        self.assertEqual(self.post().status_code,404)
        self.assertEqual(self.state(),before)

    def test_locked_week_deadline_and_conference_rules_preserved(self):
        for setup,restore in (
                ('UPDATE Week SET isLocked=true WHERE id=100','UPDATE Week SET isLocked=false'),
                ("UPDATE League SET tradeDeadline='2026-01-01'",'UPDATE League SET tradeDeadline=NULL'),
                ('UPDATE SportConference SET maxTeamsPerOwner=0','UPDATE SportConference SET maxTeamsPerOwner=3')):
            with self.subTest(setup=setup):
                self.db.connection.execute(setup)
                self.db.connection.commit()
                before=self.state()
                self.assertEqual(self.post().status_code,400)
                self.assertEqual(self.state(),before)
                self.db.connection.execute(restore)
                self.db.connection.commit()

    def test_trusted_direct_model_proposals_remain_context_free(self):
        result=self.model.propose_trade(20,200,21,22,[101],[102])
        self.assertEqual(result,{'transactionId':1,'status':'PROPOSED'})
        self.assertEqual(self.state()['Transaction'][0]['leagueId'],20)

    def test_operational_failure_returns_safe_json_and_rolls_back(self):
        before=self.state()
        def fail(sql):
            if 'INSERT INTO "Transaction"' in sql:
                raise RuntimeError('private SQL details')
        self.db.before_query=fail
        response=self.post()
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.json,{'message':'Failed to propose trade'})
        self.assertEqual(self.state(),before)
