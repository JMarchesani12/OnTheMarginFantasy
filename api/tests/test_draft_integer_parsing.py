"""Characterize real JWT/routes/domain mutations before shared parser extraction."""
import unittest
import test_live_pick_authorization as picks
import test_draft_control_authorization as controls


class DraftIntegerParsingTests(unittest.TestCase):
    def base(self, control=False):
        base=controls.DraftControlAuthorizationTests() if control else picks.LivePickAuthorizationTests()
        base.setUp();self.addCleanup(base.doCleanups)
        return base

    def test_pick_accepts_integer_string_forms_and_preserves_default_week(self):
        base=self.base()
        response=base.post({'leagueId':' +١٠ ','memberId':'  +12 ','sportTeamId':'١٠٢'})
        self.assertEqual(response.status_code,201,response.json)
        self.assertEqual((response.json['leagueId'],response.json['memberId'],response.json['sportTeamId']),(10,12,102))
        self.assertEqual(base.state()['LeagueTeamSlot'][0]['acquiredWeek'],0)

    def test_pick_malformed_fields_preserve_message_and_no_mutation(self):
        base=self.base();before=base.state()
        for field in ('leagueId','memberId','sportTeamId','weekNumber'):
            for value in (None,True,False,1.0,[],{},'','bad','1.0'):
                with self.subTest(field=field,value=value):
                    response=base.post(dict(base.body,**{field:value}))
                    self.assertEqual(response.status_code,400,response.json)
                    self.assertEqual(response.json['message'],f'{field} must be an integer')
                    self.assertEqual(base.state(),before);base.emit.assert_not_called()

    def test_pick_missing_required_fields_precede_bad_scalar(self):
        base=self.base()
        response=base.post({'leagueId':False})
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.json['message'],'Missing fields: memberId, sportTeamId')
        response=base.post(dict(base.body,weekNumber=None))
        self.assertEqual(response.json['message'],'weekNumber must be an integer')

    def test_control_strings_and_order_elements_reach_existing_domain(self):
        base=self.base(True);base.prepare('order')
        response=base.invoke('order',body={'memberIdsInOrder':[' +١٢ ','١١']})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual([r['memberId'] for r in response.json['members']],[12,11])
        base.prepare('start')
        response=base.invoke('start',body={'leagueId':' +١٠ ','actingUserId':'  +١ '})
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(response.json['state']['status'],'live')

    def test_control_malformed_actor_and_order_preserve_errors(self):
        base=self.base(True)
        for action in ('start','pause','resume','finalize','order'):
            base.prepare(action);before=base.state()
            for field in ('leagueId','actingUserId','memberId'):
                if field=='leagueId' and action=='order':continue
                if field=='memberId' and action!='order':continue
                for value in (None,True,1.5,{},[], 'bad'):
                    with self.subTest(action=action,field=field,value=value):
                        body=base.body(action)
                        if field=='memberId':body['memberIdsInOrder']=[value,11]
                        else:body[field]=value
                        response=base.invoke(action,body=body)
                        self.assertEqual(response.status_code,400,response.json)
                        self.assertEqual(response.json['message'],f'{field} must be an integer')
                        self.assertEqual(base.state(),before);base.emit.assert_not_called()

    def test_control_missing_fields_and_actor_assertion_precedence(self):
        base=self.base(True);base.prepare('finalize');before=base.state()
        response=base.invoke('finalize',body={'leagueId':False})
        self.assertEqual(response.json['message'],'Missing field: leagueId or actingUserId')
        response=base.invoke('finalize',body={'leagueId':'10','actingUserId':'2'})
        self.assertEqual(response.status_code,403)
        self.assertEqual(response.json['message'],'actingUserId does not match authenticated user')
        self.assertEqual(base.state(),before)
