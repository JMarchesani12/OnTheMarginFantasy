"""League creation policy/atomic inserts and post-commit initialization boundary."""
import copy
import unittest
from actors import UserActor
from endpoints.league.administration.service import LeagueAdminService
from endpoints.league.leagueModel import LeagueModel
import test_league_creation_authorization as creation
from test_transaction_service import ConnectionOwner


class LeagueCreationServiceTests(unittest.TestCase):
    def setUp(self):
        base=creation.LeagueCreationAuthorizationTests();base.setUp()
        self.addCleanup(base.doCleanups)
        self.db,self.payload=base.db,base.payload
        self.engine=ConnectionOwner(self.db);self.service=LeagueAdminService(self.engine)
        self.actor=UserActor(1,'alice');self.calls=[]

    def rows(self,table):
        return [dict(r) for r in self.db.connection.execute(f'SELECT * FROM "{table}" ORDER BY id')]

    def initialized(self,league_id):
        self.assertFalse(self.db.connection.in_transaction)
        self.assertEqual(self.rows('League')[0]['id'],league_id)
        self.assertEqual(len(self.rows('LeagueMember')),1)
        self.calls.append(league_id)

    def test_actor_and_required_name_before_io(self):
        self.assertTrue(callable(getattr(self.service,'create',None)), 'actor creation operation missing')
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):self.service.create(actor,self.payload(),self.initialized)
        for name in (None,42,'','  '):
            with self.assertRaises(ValueError):self.service.create(self.actor,{**self.payload(),'teamName':name},self.initialized)
        self.assertEqual(self.engine.begins,0);self.assertEqual(self.calls,[])

    def test_actor_identity_defaults_membership_and_input_immutability(self):
        self.assertTrue(hasattr(self.service,'create'), 'actor creation operation missing')
        payload=self.payload(2);before=copy.deepcopy(payload)
        result=self.service.create(self.actor,payload,self.initialized)
        self.assertEqual(payload,before);self.assertEqual(self.engine.begins,1)
        self.assertEqual(result['commissioner'],1)
        self.assertEqual(result['settings'],{'ruleSetVersion':'v1','timezone':'UTC'})
        self.assertEqual(self.calls,[result['id']])
        member=self.rows('LeagueMember')[0]
        self.assertEqual(member,{'id':result['creatorMemberId'],'leagueId':result['id'],'userId':1,
                                 'teamName':'Margin Team','seasonPoints':0,'draftOrder':1})

    def test_explicit_timezone_and_invalid_rules_fail_before_io(self):
        self.assertTrue(hasattr(self.service,'create'), 'actor creation operation missing')
        for settings in ({'timezone':'Invalid/Zone'},{'ruleSetVersion':'v2'},[]):
            with self.assertRaises(ValueError):self.service.create(self.actor,{**self.payload(),'settings':settings},self.initialized)
        self.assertEqual(self.engine.begins,0)
        result=self.service.create(self.actor,{**self.payload(),'settings':{'schedule':{'timeZone':'America/Chicago'}}},self.initialized)
        self.assertEqual(result['settings'],{'ruleSetVersion':'v1','schedule':{'timeZone':'America/Chicago'}})

    def test_failure_after_member_insert_rolls_back_both_inserts(self):
        self.assertTrue(hasattr(self.service,'create'), 'actor creation operation missing')
        execute=self.db.execute
        def fail(statement,params):
            result=execute(statement,params)
            if 'INSERT INTO "LeagueMember"' in str(statement):
                result.fetchone()
                raise RuntimeError('synthetic post-membership failure')
            return result
        self.db.execute=fail
        with self.assertRaises(RuntimeError):self.service.create(self.actor,self.payload(),self.initialized)
        self.assertEqual(self.rows('League'),[]);self.assertEqual(self.rows('LeagueMember'),[]);self.assertEqual(self.calls,[])

    def test_initializer_failure_propagates_after_committed_creation(self):
        self.assertTrue(hasattr(self.service,'create'), 'actor creation operation missing')
        def fail(league_id):
            self.initialized(league_id)
            raise RuntimeError('synthetic scheduling failure')
        with self.assertRaises(RuntimeError):self.service.create(self.actor,self.payload(),fail)
        self.assertEqual(len(self.rows('League')),1);self.assertEqual(len(self.rows('LeagueMember')),1)
        self.assertEqual(len(self.calls),1)

    def test_legacy_trusted_creator_and_deferred_schedule_access(self):
        model=LeagueModel.__new__(LeagueModel);model.db=self.engine
        with self.assertRaises(ValueError):model.create_league({'teamName':' '})
        class Schedule:
            ensure_weeks_for_league=staticmethod(self.initialized)
        model.scheduleModel=Schedule()
        row=model.create_league(self.payload(2))
        self.assertEqual(row['commissioner'],2);self.assertEqual(self.rows('LeagueMember')[0]['userId'],2)
