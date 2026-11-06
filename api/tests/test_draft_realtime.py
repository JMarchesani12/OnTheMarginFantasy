"""Real Socket.IO clients and verified synthetic JWTs; no network server started."""
import time
import unittest
from unittest.mock import patch
from flask import Flask
from flask_socketio import SocketIO
import jwt
from endpoints.draft.draftSocket import register_draft_socket_handlers
from endpoints.draft.draftBroadcast import broadcast_draft_update
from endpoints.draft.snapshot_service import DraftSnapshotService
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
import test_draft_state_authorization as fixture


class DraftRealtimeTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture.DraftStateAuthorizationTests()
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)
        self.db = self.base.db
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.io = SocketIO(self.app, async_mode='threading')
        # Injection keeps this test server isolated from the application's singleton.
        register_draft_socket_handlers(self.db, socket_server=self.io)
        self.clients = []
        self.addCleanup(self.cleanup)

    def cleanup(self):
        for client in self.clients:
            if client.is_connected(): client.disconnect()

    def token(self, subject=fixture.ALICE, **claims):
        values = dict(sub=subject, aud='authenticated', iss=ISSUER, exp=int(time.time())+600)
        values.update(claims)
        return jwt.encode(values, SUPABASE_JWT_SECRET, algorithm='HS256')

    def client(self, subject=fixture.ALICE, **claims):
        client = self.io.test_client(self.app, auth={'access_token':'Bearer '+self.token(subject, **claims)})
        self.clients.append(client)
        return client

    def join(self, client, league=10):
        client.emit('draft:join', {'leagueId':league})
        return client.get_received()

    def publish(self):
        broadcast_draft_update(10, {'type':'pick','snapshot':{'privateMarker':'private'},'pick':{'id':7}}, engine=self.db, socket_server=self.io)

    def assert_denied(self, messages):
        self.assertTrue(any(m['name']=='draft:error' for m in messages), messages)
        self.assertFalse(any(m['name'] in ('draft:snapshot','draft:updated') for m in messages), messages)
        self.assertNotIn('private', str(messages))

    def test_current_member_join_and_direct_delivery(self):
        client=self.client()
        messages=self.join(client)
        self.assertEqual(messages[0]['name'],'draft:snapshot')
        self.assertEqual(messages[0]['args'][0]['snapshot']['leagueId'],10)
        self.publish()
        self.assertEqual(client.get_received()[0]['name'],'draft:updated')

    def test_nonmember_wrong_league_and_missing_or_ambiguous_identity(self):
        for subject, league in ((fixture.OUTSIDER,10),(fixture.ALICE,20),(fixture.MISSING,10)):
            self.assert_denied(self.join(self.client(subject),league))
        self.db.connection.executescript('''
            ALTER TABLE "User" RENAME TO old_user;
            CREATE TABLE "User" AS SELECT * FROM old_user;
            INSERT INTO "User" SELECT 4, uuid, 'duplicate@example.test', 'Duplicate', "createdAt" FROM old_user WHERE id=1;
        ''')
        self.db.connection.commit()
        self.assert_denied(self.join(self.client()))

    def test_connect_rejects_expired_missing_exp_and_missing_token(self):
        for claims in ({'exp':1},{'exp':None}):
            client=self.client(**claims)
            self.assertFalse(client.is_connected())
        self.assertFalse(self.io.test_client(self.app,auth={}).is_connected())

    def test_removed_member_evicted_before_direct_and_cannot_rejoin(self):
        client=self.client();self.join(client)
        self.db.connection.execute('DELETE FROM "LeagueMember" WHERE id=11');self.db.connection.commit()
        self.publish();self.assert_denied(client.get_received())
        self.assert_denied(self.join(client))
        self.publish();self.assertEqual(client.get_received(),[])

    def test_expired_session_is_checked_again_on_delivery(self):
        client=self.client();self.join(client)
        with patch('jwt.api_jwt.datetime') as clock:
            from datetime import datetime, timezone
            clock.now.return_value=datetime.fromtimestamp(time.time()+3600,timezone.utc)
            self.publish()
        self.assert_denied(client.get_received())

    def test_revocation_between_snapshot_and_initial_delivery(self):
        client=self.client();original=DraftSnapshotService.snapshot_for_reader_id
        def revoke(service,*args,**kwargs):
            result=original(service,*args,**kwargs)
            self.db.connection.execute('DELETE FROM "LeagueMember" WHERE id=11');self.db.connection.commit()
            return result
        with patch.object(DraftSnapshotService,'snapshot_for_reader_id',revoke):
            self.assert_denied(self.join(client))
        self.publish();self.assertEqual(client.get_received(),[])

    def test_lookup_and_snapshot_errors_are_safe(self):
        client=self.client();self.join(client)
        def fail(sql): raise RuntimeError('private SQL token details')
        self.db.before_query=fail
        self.publish();self.assert_denied(client.get_received())
        self.db.before_query=None
        with patch.object(DraftSnapshotService,'snapshot_for_reader_id',side_effect=RuntimeError('private SQL token details')):
            self.assert_denied(self.join(client))

    def test_leave_after_revocation_and_disconnect_clear_subscription(self):
        client=self.client();self.join(client)
        self.db.connection.execute('DELETE FROM "LeagueMember" WHERE id=11');self.db.connection.commit()
        client.emit('draft:leave',{'leagueId':10})
        self.assertEqual(client.get_received(),[])
        self.publish();self.assertEqual(client.get_received(),[])
        client.disconnect()
        self.assertEqual(self.io.draft_access.tokens,{})

    def test_invalid_ids_do_not_join(self):
        client=self.client()
        for value in (None,True,1.2,0,-1,2**63,'oops'):
            messages=self.join(client,value)
            self.assertTrue(any(m['name']=='draft:error' for m in messages))
            self.assertFalse(any(m['name']=='draft:snapshot' for m in messages))

    def test_listener_uses_same_guard_and_reconnect_fetches_current_state(self):
        from endpoints.draft.startDraftNotifyListener import dispatch_draft_notification
        alice=self.client();bob=self.client(fixture.BOB)
        self.join(alice);self.join(bob)
        self.db.connection.execute('DELETE FROM "LeagueMember" WHERE id=11');self.db.connection.commit()
        dispatch_draft_notification(self.io,self.db,{'leagueId':10})
        self.assert_denied(alice.get_received())
        messages=bob.get_received();self.assertEqual(messages[0]['args'][0]['type'],'notify')
        bob.disconnect()
        new=self.client(fixture.BOB)
        self.assertEqual(self.join(new)[0]['args'][0]['snapshot']['members'][0]['userId'],2)

    def test_unregistered_broadcast_has_no_unchecked_fallback(self):
        other=SocketIO(Flask('unregistered'),async_mode='threading')
        with patch.object(other,'emit') as emit:
            broadcast_draft_update(10,{'snapshot':{'privateMarker':1}},engine=self.db,socket_server=other)
            emit.assert_not_called()

    def test_expiry_during_membership_lookup_blocks_direct_and_listener_delivery(self):
        from endpoints.draft.startDraftNotifyListener import dispatch_draft_notification
        for listener in (False,True):
            with self.subTest(listener=listener):
                client=self.client();self.join(client)
                now=time.time()
                with patch('endpoints.draft.realtime.time.time',return_value=now) as clock:
                    def expire(sql):
                        if 'WHERE "leagueId"=:leagueId AND "userId"=:userId' in sql:
                            clock.return_value=now+3600
                    self.db.before_query=expire
                    try:
                        if listener:dispatch_draft_notification(self.io,self.db,{'leagueId':10})
                        else:self.publish()
                    finally:self.db.before_query=None
                    messages=client.get_received()
                client.disconnect()
                self.assert_denied(messages)
