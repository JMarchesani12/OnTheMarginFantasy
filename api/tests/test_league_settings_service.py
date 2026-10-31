"""League update authority, settings policy and transaction compatibility."""
import copy
import unittest
from actors import UserActor
from endpoints.league.administration.service import LeagueAdminService
from endpoints.league.leagueModel import LeagueModel
import test_league_settings_authorization as settings
from test_transaction_service import ConnectionOwner


class LeagueSettingsServiceTests(unittest.TestCase):
    def setUp(self):
        base=settings.LeagueSettingsAuthorizationTests();base.setUp()
        self.addCleanup(base.doCleanups)
        self.db,self.league=base.db,base.league
        self.engine=ConnectionOwner(self.db);self.service=LeagueAdminService(self.engine)
        self.actor=UserActor(1,'alice')

    def test_actor_required_before_io(self):
        self.assertTrue(callable(getattr(self.service,'update',None)), 'actor update operation missing')
        for actor in (None,1,{'user_id':1}):
            with self.assertRaises(TypeError):self.service.update(actor,10,{'name':'Forged'})
        self.assertEqual(self.engine.begins,0)

    def test_two_scopes_projection_allowlist_and_patch_immutability(self):
        self.assertTrue(hasattr(self.service,'update'), 'actor update operation missing')
        patch={'name':"O'Brien :name",'numPlayers':9,'settings':{'schedule':{'timeZone':'America/Chicago'},'bonuses':{}},
               'draftDate':'2026-11-01T12:00:00Z','tradeDeadline':None,'freeAgentDeadline':'2027-01-01T12:00:00Z',
               'commissioner':2,'sport':2};before=copy.deepcopy(patch)
        row=self.service.update(self.actor,10,patch)
        self.assertEqual(self.engine.begins,2);self.assertEqual(patch,before)
        self.assertEqual(set(row),{'id','createdAt','name','sport','numPlayers','status','settings','updatedAt','draftDate',
                                   'freeAgentDeadline','tradeDeadline','commissioner','sportInfo'})
        self.assertEqual((row['name'],row['commissioner'],row['sport'],row['numPlayers']),("O'Brien :name",1,1,9))
        self.assertEqual(row['settings'],{'schedule':{'timeZone':'America/Chicago'},'bonuses':{},'ruleSetVersion':'v1'})
        self.assertEqual(row['sportInfo'],{'id':1,'name':'Basketball'})

    def test_authority_and_missing_precede_settings_validation(self):
        self.assertTrue(hasattr(self.service,'update'), 'actor update operation missing')
        before=self.league()
        with self.assertRaises(PermissionError):self.service.update(UserActor(2,'bob'),10,{'settings':[]})
        with self.assertRaisesRegex(ValueError,'League 999 not found'):self.service.update(self.actor,999,{'settings':[]})
        self.assertEqual(self.league(),before)

    def test_empty_version_timezone_errors_do_not_write(self):
        self.assertTrue(hasattr(self.service,'update'), 'actor update operation missing')
        before=self.league()
        for patch in ({},{'sport':2},{'settings':[]},{'settings':{'ruleSetVersion':'v2'}},
                      {'settings':{'schedule':{'timezone':'Invalid/Zone'},'timezone':'UTC'}}):
            with self.assertRaises(ValueError):self.service.update(self.actor,10,patch)
            self.assertEqual(self.league(),before)
        self.assertEqual(self.engine.begins,5)

    def test_write_predicate_rejects_late_authority_change(self):
        self.assertTrue(hasattr(self.service,'update'), 'actor update operation missing')
        before=self.league()
        self.db.before_update=lambda:self.db.connection.execute('UPDATE "League" SET commissioner=2 WHERE id=10')
        with self.assertRaises(PermissionError):self.service.update(self.actor,10,{'name':'Stale'})
        self.assertEqual(self.league(),{**before,'commissioner':2})

    def test_post_update_failure_rolls_back(self):
        self.assertTrue(hasattr(self.service,'update'), 'actor update operation missing')
        before=self.league();execute=self.db.execute
        def fail(statement,params):
            result=execute(statement,params)
            if 'WITH updated AS' in str(statement):
                result.mappings().first()
                raise RuntimeError('synthetic post-update failure')
            return result
        self.db.execute=fail
        with self.assertRaises(RuntimeError):self.service.update(self.actor,10,{'name':'Failed'})
        self.assertEqual(self.league(),before)

    def test_db_only_trusted_private_and_timezone_helpers_remain_compatible(self):
        model=LeagueModel.__new__(LeagueModel);model.db=self.engine
        self.assertEqual(model.update_league(20,{'name':'Trusted'})['name'],'Trusted')
        with self.assertRaises(PermissionError):model._update_league(10,{'name':'Denied'},commissioner_id=2)
        self.assertEqual(model._update_league(10,{'name':'Private'})['name'],'Private')
        self.assertEqual(model._get_timezone_name_from_settings({'schedule':{'timeZone':'UTC'},'timezone':'Invalid'}),'UTC')
        with self.assertRaises(ValueError):model._validate_timezone_name('Invalid/Zone')
        self.assertEqual(model._ensure_timezone_in_settings({}),{'timezone':'UTC'})
