"""Public scalar and existing wrappers share the pure parser; adapters call it."""
import unittest
from unittest.mock import patch
from utils import requestValidation as validation
import test_draft_control_authorization as controls

class IntegerValueTests(unittest.TestCase):
    def test_scalar_keeps_python_integer_forms_and_ranges(self):
        self.assertTrue(callable(getattr(validation,'integer_value',None)),'public scalar parser missing')
        for value,expected in ((0,0),(-1,-1),(2**100,2**100),(' +١٠ ',10),('-3',-3),('1_000',1000)):
            self.assertEqual(validation.integer_value(value,'id'),expected)
        for value in (None,True,False,1.0,{},[],(),'', 'bad','1.0'):
            with self.assertRaisesRegex(ValueError,'^id must be an integer$'):validation.integer_value(value,'id')

    def test_existing_wrappers_keep_missing_empty_duplicates_and_ceiling(self):
        self.assertTrue(callable(getattr(validation,'integer_value',None)),'public scalar parser missing')
        with self.assertRaisesRegex(ValueError,'^id must be an integer$'):validation.integer_field({},'id')
        self.assertEqual(validation.integer_list_field({'ids':[]},'ids'),[])
        self.assertEqual(validation.integer_list_field({'ids':['2','2',-1]},'ids'),[2,2,-1])
        with self.assertRaisesRegex(ValueError,'at most 2 items'):validation.integer_list_field({'ids':[1,2,3]},'ids',max_items=2)
        with patch.object(validation,'integer_value',wraps=validation.integer_value) as scalar:
            validation.integer_field({'id':'7'},'id')
            validation.integer_list_field({'ids':['8']},'ids')
            self.assertEqual(scalar.call_args_list,[unittest.mock.call('7','id'),unittest.mock.call('8','ids')])

    def test_real_draft_consumers_use_shared_scalar(self):
        from endpoints.draft import draftEndpoints
        self.assertTrue(hasattr(draftEndpoints,'integer_value'),'draft consumers still define local parsers')
        base=controls.DraftControlAuthorizationTests();base.setUp();self.addCleanup(base.doCleanups)
        with patch.object(draftEndpoints,'integer_value',wraps=validation.integer_value) as scalar:
            response=base.fixture.post()
            self.assertEqual(response.status_code,201,response.json)
            self.assertEqual(scalar.call_args_list,[unittest.mock.call(10,'leagueId'),unittest.mock.call(12,'memberId'),unittest.mock.call(102,'sportTeamId'),unittest.mock.call(0,'weekNumber')])
            scalar.reset_mock();base.prepare('order')
            self.assertEqual(base.invoke('order').status_code,200)
            self.assertEqual(scalar.call_args_list,[unittest.mock.call('12','memberId'),unittest.mock.call('11','memberId')])
            scalar.reset_mock();base.prepare('start')
            self.assertEqual(base.invoke('start',body={'leagueId':'10','actingUserId':'1'}).status_code,200)
            self.assertEqual(scalar.call_args_list,[unittest.mock.call('10','leagueId'),unittest.mock.call('1','actingUserId')])
