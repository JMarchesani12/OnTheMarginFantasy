"""Transaction reads: real JWT/routes/SQL, isolated SQLite aggregation adapter.

Open-list JSONB aggregation/expansion uses SQLite json functions. Pending-list
LATERAL aggregates become correlated scalar aggregates. Authorization WHERE
clauses, joins, filters, grouping and ordering execute unchanged. Not PostgreSQL
query/RLS/locking verification.
"""
import datetime as dt
import json
import re
import unittest
from sqlalchemy import text
import test_free_agency_authorization as fixture


class TransactionReadDatabase(fixture.TransactionDatabase):
    def execute(self, statement, params=None):
        sql=str(statement)
        for column,alias in (('fromTeamIds','ft'),('toTeamIds','tt')):
            if 'LEFT JOIN LATERAL (' in sql:
                field='fromTeams' if column=='fromTeamIds' else 'toTeams'
                sql=sql.replace(f'{alias}."{field}"',f'''(
                    SELECT json_group_array(json_object('id', ordered.id,'displayName',ordered."displayName"))
                    FROM (SELECT st.id,st."displayName" FROM json_each(t."{column}") ids
                          JOIN "SportTeam" st ON st.id=CAST(ids.value AS INTEGER)
                          ORDER BY st."displayName") ordered
                ) AS "{field}"''')
                sql=re.sub(r'LEFT JOIN LATERAL \(.*?\) '+alias+r' ON TRUE','',sql,count=1,flags=re.S)
        for column,alias in (('fromTeamIds','f'),('toTeamIds','tt')):
            sql=sql.replace(f'LEFT JOIN LATERAL jsonb_array_elements_text(t."{column}") AS {alias}(team_id)',
                            f'LEFT JOIN json_each(t."{column}") {alias}')
            sql=sql.replace(f'{alias}.team_id::bigint',f'CAST({alias}.value AS INTEGER)')
        sql=sql.replace('jsonb_agg(', 'json_group_array(').replace('jsonb_build_object(', 'json_object(').replace("'[]'::jsonb","'[]'")
        result=super().execute(text(sql),params)
        original_all=result.all
        def decoded_all():
            rows=original_all()
            for row in rows:
                for field in ('fromTeams','toTeams'):
                    if isinstance(row.get(field),str):
                        row[field]=json.loads(row[field])
                if isinstance(row.get('createdAt'),str):
                    row['createdAt']=dt.datetime.fromisoformat(row['createdAt'])
            return rows
        result.all=decoded_all
        return result


class TransactionReadAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.FreeAgencyAuthorizationTests()
        self.fixture.database_type=TransactionReadDatabase
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db,self.client,self.model=self.fixture.db,self.fixture.client,self.fixture.model
        self.headers,self.state=self.fixture.headers,self.fixture.state
        self.db.connection.executescript('''
            ALTER TABLE League ADD COLUMN isDiscoverable BOOLEAN DEFAULT true;
            INSERT INTO League VALUES (30,1,'{}',NULL,true);
            ALTER TABLE LeagueMember ADD COLUMN teamName TEXT;
            UPDATE LeagueMember SET teamName='Alice' WHERE userId=1;
            UPDATE LeagueMember SET teamName='Bob' WHERE userId=2;
            INSERT INTO "User" (id,uuid,displayName) VALUES (3,'voter','Voter'),(4,'nonmember','Nonmember');
            INSERT INTO LeagueMember VALUES (13,10,3,'Voter');
            CREATE TABLE SportTeam (id INTEGER,displayName TEXT);
            INSERT INTO SportTeam VALUES (101,'Alpha'),(102,'Bravo'),(103,'Charlie');
            CREATE TABLE TransactionVote (transactionId INTEGER,leagueMemberId INTEGER,veto BOOLEAN);
            INSERT INTO TransactionVote VALUES (1,13,true);
            ALTER TABLE "Transaction" ADD COLUMN createdAt TEXT DEFAULT '2026-10-29T12:00:00';
            INSERT INTO "Transaction" (id,leagueId,weekId,type,memberFromId,memberToId,status,fromTeamIds,toTeamIds)
            VALUES (1,10,100,'TRADE',11,12,'PROPOSED','[101]','[102]'),
                   (2,10,100,'FREE_AGENT',11,11,'PENDING_APPLY','[]','[103]'),
                   (3,10,100,'TRADE',12,11,'PENDING_APPLY','[102]','[101]'),
                   (4,10,100,'TRADE',11,12,'REJECTED','[101]','[102]'),
                   (5,20,200,'TRADE',21,21,'PENDING_APPLY','[101]','[102]');
        ''')

    def open(self, member=11,subject=fixture.ALICE,league=10,**extra):
        return self.client.post(f'/api/league/{league}/transactions/trades/open',
            headers=self.headers(subject),json=dict(memberId=member,**extra))

    def pending(self,league=10,subject=fixture.ALICE,query=''):
        return self.client.get(f'/api/league/{league}/transaction/pending{query}',headers=self.headers(subject))

    def test_open_reads_preserve_personalization_others_votes_and_fields(self):
        response=self.open(member='11')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json['memberId'],11)
        self.assertEqual([row['transactionId'] for row in response.json['mine']['incoming']],[3])
        outgoing=response.json['mine']['outgoing']
        self.assertEqual([row['transactionId'] for row in outgoing],[1])
        self.assertEqual(outgoing[0],dict(transactionId=1,leagueId=10,weekId=100,type='TRADE',status='PROPOSED',
            memberFromId=11,memberToId=12,memberFromTeamName='Alice',memberFromDisplayName='Alice',
            memberToTeamName='Bob',memberToDisplayName='Bob',fromTeams=[{'id':101,'displayName':'Alpha'}],
            toTeams=[{'id':102,'displayName':'Bravo'}],memberHasVetoed=False,isParticipant=True,vetoCount=1,
            createdAt='2026-10-29T12:00:00'))
        voter=self.open(13,'voter')
        self.assertEqual(voter.status_code,200)
        self.assertEqual(voter.json['mine'],{'incoming':[],'outgoing':[]})
        self.assertEqual({row['transactionId'] for row in voter.json['others']},{1,3})
        self.assertTrue(next(row for row in voter.json['others'] if row['transactionId']==1)['memberHasVetoed'])

    def test_open_member_impersonation_and_cross_league_reads_denied(self):
        for member,subject,league in ((12,fixture.ALICE,10),(11,fixture.BOB,10),(13,'nonmember',10),
                                     (21,fixture.ALICE,20),(21,fixture.BOB,10),(11,fixture.ALICE,999),
                                     (999,fixture.ALICE,10)):
            with self.subTest(member=member,subject=subject,league=league):
                self.db.queries.clear()
                response=self.open(member,subject,league,trustedJob=True,actingUserId=2,userId=2)
                self.assertEqual(response.status_code,404)
                self.assertFalse(any('FROM "Transaction" t' in sql for sql in self.db.queries))

    def test_pending_member_and_commissioner_reads_keep_filters_and_fields(self):
        for subject in (fixture.ALICE,fixture.BOB,'voter'):
            response=self.pending(subject=subject)
            self.assertEqual(response.status_code,200)
            self.assertEqual([row['id'] for row in response.json],[3,2])
            self.assertTrue(all(row['leagueId']==10 for row in response.json))
            self.assertEqual(set(response.json[0]),{'id','leagueId','weekId','weekNumber','type','status',
                'memberFromId','memberToId','memberFromDisplayName','memberToDisplayName','fromTeams','toTeams','createdAt'})
            self.assertEqual(response.json[0]['fromTeams'],[{'id':102,'displayName':'Bravo'}])
        self.assertEqual([row['id'] for row in self.pending(query='?status=PROPOSED').json],[1])
        self.assertEqual(self.pending(30).status_code,200)  # commissioner without membership
        self.assertEqual(self.pending(30).json,[])
        self.assertEqual([row['id'] for row in self.pending(20,fixture.BOB).json],[5])

    def test_pending_nonmembers_discoverable_and_cross_league_denied(self):
        for league,subject in ((10,'nonmember'),(20,fixture.ALICE),(30,fixture.BOB),(999,fixture.ALICE)):
            with self.subTest(league=league,subject=subject):
                self.db.queries.clear()
                response=self.pending(league,subject,'?memberId=21&userId=2&trustedJob=true')
                self.assertEqual(response.status_code,404)
                self.assertFalse(any('FROM "Transaction" t' in sql for sql in self.db.queries))

    def test_late_authority_loss_in_final_queries_exposes_no_data(self):
        def revoke(sql):
            if 'FROM "Transaction" t' in sql:
                self.db.before_query=None
                self.db.connection.execute('DELETE FROM LeagueMember WHERE id=12')
        for reader in (lambda:self.open(12,fixture.BOB),lambda:self.pending(subject=fixture.BOB)):
            self.db.before_query=revoke
            response=reader()
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json,[] if isinstance(response.json,list) else
                             {'memberId':12,'mine':{'incoming':[],'outgoing':[]},'others':[]})
            self.db.connection.execute("INSERT INTO LeagueMember VALUES (12,10,2,'Bob')")
            self.db.connection.commit()

    def test_auth_and_missing_profile_denied_on_both_routes(self):
        for path,method,body in (('/api/league/10/transactions/trades/open','post',{'memberId':11}),
                                ('/api/league/10/transaction/pending','get',None)):
            for headers,status in (({},401),({'Authorization':'Bearer invalid'},401),
                                   (self.headers(exp=1),401),(self.headers('missing'),403)):
                response=getattr(self.client,method)(path,headers=headers,json=body)
                self.assertEqual(response.status_code,status)

    def test_malformed_open_requests_are_400(self):
        for value in (True,1.5,[],{},None,'bad'):
            self.assertEqual(self.open(value).status_code,400)
        self.assertEqual(self.client.post('/api/league/10/transactions/trades/open',json=[],headers=self.headers()).status_code,400)

    def test_trusted_model_calls_remain_context_free(self):
        self.assertEqual(self.model.get_open_trade_transactions_for_member(20,21)['memberId'],21)
        rows=self.model.get_transactions_for_league(20)
        self.assertEqual([row['id'] for row in rows],[5])
        self.assertEqual(self.model.get_transactions_for_league(999),[])

    def test_database_failures_return_safe_errors_and_reads_do_not_mutate(self):
        before=self.state()
        def fail(sql):
            if 'FROM "Transaction" t' in sql:
                raise RuntimeError('private SQL details')
        self.db.before_query=fail
        for read in (self.open,self.pending):
            response=read()
            self.assertEqual(response.status_code,500)
            self.assertNotIn('private SQL details',str(response.json))
        self.assertEqual(self.state(),before)

    def test_ambiguous_profile_denied_on_both_reads(self):
        self.db.connection.executescript('''
            ALTER TABLE "User" RENAME TO old_user;
            CREATE TABLE "User" AS SELECT * FROM old_user;
            INSERT INTO "User" SELECT 5,uuid,'duplicate@example.test','Duplicate',createdAt FROM old_user WHERE id=1;
        ''')
        self.assertEqual(self.open().status_code,403)
        self.assertEqual(self.pending().status_code,403)

    def test_commissioner_revocation_before_pending_query_exposes_nothing(self):
        def revoke(sql):
            if 'FROM "Transaction" t' in sql:
                self.db.before_query=None
                self.db.connection.execute('UPDATE League SET commissioner=2 WHERE id=20')
        # Alice is commissioner without membership in 20 for this subcase.
        self.db.connection.execute('UPDATE League SET commissioner=1 WHERE id=20')
        self.db.before_query=revoke
        response=self.pending(20)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json,[])

    def test_all_terminal_statuses_are_excluded_from_open_reads(self):
        for status in ('COMPLETED','REJECTED','CANCELLED','VETOED'):
            self.db.connection.execute('UPDATE "Transaction" SET status=? WHERE id=1',(status,))
            response=self.open()
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json['mine']['outgoing'],[])
            self.assertEqual([row['transactionId'] for row in response.json['mine']['incoming']],[3])
