"""Response/cancellation: real JWT/routes/SQL using the isolated transaction fixture.

FOR UPDATE is removed and JSONB arrays decoded to match psycopg rows. SQLite
cannot verify PostgreSQL row locks, RLS or concurrent authorization revocation.
"""
import json
import unittest
from sqlalchemy import text
import test_free_agency_authorization as fixture
from test_league_read_authorization import ReadRow


class TradeActionDatabase(fixture.TransactionDatabase):
    def execute(self, statement, params=None):
        result=super().execute(text(str(statement).replace('FOR UPDATE','')),params)
        fetchone=result.fetchone
        def decoded_row():
            row=fetchone()
            if row is None:
                return None
            values=dict(row._mapping)
            for column in ('fromTeamIds','toTeamIds'):
                if isinstance(values.get(column),str):
                    values[column]=json.loads(values[column])
            return ReadRow(values)
        result.fetchone=decoded_row
        return result


class TradeActionAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.FreeAgencyAuthorizationTests()
        self.fixture.database_type=TradeActionDatabase
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db,self.client,self.model=self.fixture.db,self.fixture.client,self.fixture.model
        self.state,self.headers=self.fixture.state,self.fixture.headers
        self.db.connection.executescript('''
            ALTER TABLE League ADD COLUMN tradeDeadline TEXT;
            ALTER TABLE "Transaction" ADD COLUMN decidedByMemberId INTEGER;
            ALTER TABLE "Transaction" ADD COLUMN rejectReason TEXT;
            INSERT INTO LeagueMember VALUES (22,20,1),(13,10,3);
            INSERT INTO "User" (id,uuid) VALUES (3,'outsider');
            INSERT INTO LeagueTeamSlot VALUES (4,20,22,102,1,NULL,'Draft');
            INSERT INTO "Transaction" (id,leagueId,weekId,type,memberFromId,memberToId,status,fromTeamIds,toTeamIds)
                VALUES (1,10,100,'TRADE',11,12,'PROPOSED','[101]','[102]'),
                       (2,20,200,'TRADE',22,21,'PROPOSED','[102]','[101]');
        ''')

    def post(self, operation='respond', *, league=10, tx=1, member=None, subject=None, action='ACCEPT', **extras):
        responder=operation=='respond'
        member=(12 if responder else 11) if member is None else member
        subject=(fixture.BOB if responder else fixture.ALICE) if subject is None else subject
        body={('responderMemberId' if responder else 'requesterMemberId'):member,**extras}
        if responder:
            body.update(action=action,rejectReason='No thanks')
        return self.client.post(f'/api/league/{league}/transaction/{tx}/trade/{operation}',
                                json=body,headers=self.headers(subject))

    def reset(self):
        self.db.connection.execute('''UPDATE "Transaction" SET status='PROPOSED',
            decidedByMemberId=NULL,rejectReason=NULL''')
        self.db.connection.commit()

    def test_legitimate_accept_reject_and_cancel_preserve_contracts_and_roster(self):
        for operation,action,status,actor in (('respond','ACCEPT','PENDING_APPLY',12),
                ('respond','REJECT','REJECTED',12),('cancel','ACCEPT','CANCELLED',11)):
            with self.subTest(operation=operation,action=action):
                self.reset()
                before=self.state()
                response=self.post(operation,action=action,member=str(actor))
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json,{'transactionId':1,'status':status})
                after=self.state()
                self.assertEqual((after['Transaction'][0]['status'],after['Transaction'][0]['decidedByMemberId']),
                                 (status,actor))
                self.assertEqual(after['Transaction'][0]['rejectReason'],'No thanks' if action=='REJECT' else None)
                self.assertEqual(after['Transaction'][1],before['Transaction'][1])
                self.assertEqual(after['LeagueTeamSlot'],before['LeagueTeamSlot'])

    def test_same_league_impersonation_commissioner_and_wrong_party_denied(self):
        cases=(('respond',12,fixture.ALICE),('respond',11,fixture.ALICE),('respond',13,'outsider'),
               ('cancel',11,fixture.BOB),('cancel',12,fixture.BOB),('cancel',13,'outsider'))
        for operation,member,subject in cases:
            with self.subTest(operation=operation,member=member,subject=subject):
                self.reset()
                before=self.state()
                response=self.post(operation,member=member,subject=subject,trustedJob=True,actingUserId=2,userId=2)
                self.assertEqual(response.status_code,404)
                self.assertEqual(response.json,{'message':'Trade not found'})
                self.assertEqual(self.state(),before)

    def test_correct_transaction_under_wrong_url_league_and_foreign_member_denied(self):
        for operation in ('respond','cancel'):
            for league,tx,member,subject in ((20,1,12,fixture.BOB),(10,2,21,fixture.BOB),
                    (10,1,21,fixture.BOB),(10,999,12,fixture.BOB),(999,1,12,fixture.BOB)):
                with self.subTest(operation=operation,league=league,tx=tx,member=member):
                    self.reset()
                    before=self.state()
                    self.db.queries.clear()
                    response=self.post(operation,league=league,tx=tx,member=member,subject=subject)
                    self.assertEqual(response.status_code,404)
                    self.assertEqual(self.state(),before)
                    self.assertFalse(any('FROM "Week"' in sql or 'FROM "LeagueTeamSlot"' in sql for sql in self.db.queries))

    def test_second_league_legitimate_actions_remain_scoped(self):
        for operation,member,subject,status in (('respond',21,fixture.BOB,'PENDING_APPLY'),
                                               ('cancel',22,fixture.ALICE,'CANCELLED')):
            self.reset()
            response=self.post(operation,league=20,tx=2,member=member,subject=subject)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json,{'transactionId':2,'status':status})
            self.assertEqual(self.state()['Transaction'][0]['status'],'PROPOSED')

    def test_auth_missing_and_ambiguous_profiles_fail_without_writes(self):
        before=self.state()
        for operation in ('respond','cancel'):
            for headers,status in (({},401),({'Authorization':'Bearer invalid'},401),
                                   (self.headers(exp=1),401),(self.headers('missing'),403)):
                response=self.client.post(f'/api/league/10/transaction/1/trade/{operation}',
                    json={'action':'ACCEPT','responderMemberId':12,'requesterMemberId':11},headers=headers)
                self.assertEqual(response.status_code,status)
        self.db.connection.executescript('''
            ALTER TABLE "User" RENAME TO old_user;
            CREATE TABLE "User" AS SELECT * FROM old_user;
            INSERT INTO "User" SELECT 4,uuid,'duplicate@example.test','Duplicate',createdAt FROM old_user WHERE id=2;
        ''')
        self.assertEqual(self.post().status_code,403)
        self.assertEqual(self.post('cancel',subject=fixture.BOB).status_code,403)
        self.assertEqual(self.state(),before)

    def test_malformed_bodies_and_integer_actors_rejected(self):
        before=self.state()
        for operation in ('respond','cancel'):
            for value in (True,1.5,[],{},'bad'):
                self.assertEqual(self.post(operation,member=value).status_code,400)
            for body in ([],{},None):
                response=self.client.post(f'/api/league/10/transaction/1/trade/{operation}',
                    json=body,headers=self.headers())
                self.assertEqual(response.status_code,400)
        self.assertEqual(self.post(action=[]).status_code,400)
        self.assertEqual(self.state(),before)

    def test_existing_resolved_and_invalid_action_rejections_unchanged(self):
        self.assertEqual(self.post(action='invalid').status_code,400)
        for operation in ('respond','cancel'):
            for status in ('PENDING_APPLY','REJECTED','CANCELLED'):
                self.db.connection.execute('UPDATE "Transaction" SET status=? WHERE id=1',(status,))
                self.db.connection.commit()
                before=self.state()
                self.assertEqual(self.post(operation).status_code,400)
                self.assertEqual(self.state(),before)

    def test_accept_domain_rules_preserved_reject_cancel_still_allowed(self):
        for setup,restore in (
                ("UPDATE League SET tradeDeadline='2026-01-01'",'UPDATE League SET tradeDeadline=NULL'),
                ('UPDATE Week SET isLocked=true','UPDATE Week SET isLocked=false'),
                ('UPDATE SportConference SET maxTeamsPerOwner=0','UPDATE SportConference SET maxTeamsPerOwner=3'),
                ('UPDATE LeagueTeamSlot SET memberId=13 WHERE id=1','UPDATE LeagueTeamSlot SET memberId=11 WHERE id=1')):
            with self.subTest(setup=setup):
                self.reset()
                self.db.connection.execute(setup)
                self.db.connection.commit()
                before=self.state()
                self.assertEqual(self.post().status_code,400)
                self.assertEqual(self.state(),before)
                self.assertEqual(self.post(action='REJECT').status_code,200)
                self.reset()
                self.assertEqual(self.post('cancel').status_code,200)
                self.db.connection.execute(restore)
                self.db.connection.commit()

    def test_late_owner_or_transaction_scope_loss_rolls_back_each_action(self):
        for operation,action,member in (('respond','ACCEPT',12),('respond','REJECT',12),('cancel','ACCEPT',11)):
            for mutation in (f'UPDATE LeagueMember SET userId=99 WHERE id={member}',
                             'UPDATE "Transaction" SET leagueId=20 WHERE id=1',
                             f'UPDATE "Transaction" SET {"memberToId" if operation=="respond" else "memberFromId"}=13 WHERE id=1'):
                with self.subTest(operation=operation,action=action,mutation=mutation):
                    self.reset()
                    before=self.state()
                    def revoke(sql):
                        if 'UPDATE "Transaction"' in sql:
                            self.db.before_query=None
                            self.db.connection.execute(mutation)
                    self.db.before_query=revoke
                    response=self.post(operation,action=action)
                    self.assertEqual(response.status_code,404)
                    self.assertEqual(self.state(),before)
                    self.assertEqual(self.db.connection.execute('SELECT userId FROM LeagueMember WHERE id=?',(member,)).fetchone()[0],
                                     2 if member==12 else 1)

    def test_trusted_calls_remain_context_free_with_existing_party_rules(self):
        self.assertEqual(self.model.respond_to_trade(2,'ACCEPT',21),{'transactionId':2,'status':'PENDING_APPLY'})
        self.reset()
        self.assertEqual(self.model.respond_to_trade(2,'REJECT',21,'Trusted rejection'),{'transactionId':2,'status':'REJECTED'})
        self.reset()
        self.assertEqual(self.model.cancel_trade_proposal(2,22),{'transactionId':2,'status':'CANCELLED'})
        self.reset()
        with self.assertRaises(ValueError):
            self.model.cancel_trade_proposal(2,11)
        with self.assertRaises(ValueError):
            self.model.respond_to_trade(2,'ACCEPT',12)

    def test_database_failure_returns_safe_json_and_rolls_back(self):
        for operation in ('respond','cancel'):
            self.reset()
            before=self.state()
            def fail(sql):
                if 'UPDATE "Transaction"' in sql:
                    raise RuntimeError('private SQL details')
            self.db.before_query=fail
            response=self.post(operation)
            self.db.before_query=None
            self.assertEqual(response.status_code,500)
            self.assertEqual(response.json,{'message':'Failed to respond to trade' if operation=='respond' else 'Failed to cancel trade'})
            self.assertEqual(self.state(),before)

    def test_partial_actor_context_cannot_fall_back_to_trusted_access(self):
        before=self.state()
        for context in ({'league_id':10},{'acting_user_id':2}):
            with self.assertRaises(ValueError):
                self.model.respond_to_trade(1,'REJECT',12,**context)
            with self.assertRaises(ValueError):
                self.model.cancel_trade_proposal(1,11,**context)
        self.assertEqual(self.state(),before)

    def test_nontrade_cancellation_rejection_is_preserved(self):
        self.db.connection.execute("UPDATE \"Transaction\" SET type='FREE_AGENT' WHERE id=1")
        self.db.connection.commit()
        before=self.state()
        self.assertEqual(self.post('cancel').status_code,400)
        self.assertEqual(self.state(),before)
