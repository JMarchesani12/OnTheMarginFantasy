"""Commissioner draft controls: actual JWT/routes/transaction SQL, synthetic DB."""
import json
import unittest

from sqlalchemy import text

import test_live_pick_authorization as live_fixture
import test_draft_state_authorization as identities


class ControlDatabase(live_fixture.LivePickDatabase):
    def execute(self, statement, params):
        sql = str(statement)
        sql = sql.replace('FROM generate_series(1, :numPlayers) gs', '''FROM (
            WITH RECURSIVE series(gs) AS (
                SELECT 1 UNION ALL SELECT gs + 1 FROM series WHERE gs < :numPlayers
            ) SELECT gs FROM series
        )''')
        if isinstance(params, list):
            self.queries.append(sql)
            if self.before_query:
                self.before_query(sql)
            self.connection.executemany(sql, params)
            return None  # seed_draft_turns ignores the executemany result.
        params = dict(params)
        if 'ids' in params:
            params['ids'] = json.dumps(params['ids'])
        sql = sql.replace('id = ANY(CAST(:ids AS bigint[]))', 'id IN (SELECT value FROM json_each(:ids))')
        if 'unnest(CAST(:ids AS bigint[]))' in sql:
            sql = '''WITH input AS (
                SELECT CAST(value AS INTEGER) AS member_id, CAST(key AS INTEGER) + 1 AS new_order
                FROM json_each(:ids)
            ) UPDATE "LeagueMember" AS lm SET "draftOrder" = i.new_order
              FROM input i WHERE lm.id = i.member_id AND lm."leagueId" = :leagueId'''
        sql = sql.replace('UPDATE "League" l', 'UPDATE "League" AS l')
        sql = sql.replace('ss."seasonEnd"::date', 'date(ss."seasonEnd")').replace(
            'ss."seasonStart"::date', 'date(ss."seasonStart")').replace('now()::date', 'date(now())')
        sql = sql.replace('RETURNING l.id AS "leagueId", l.status AS "leagueStatus"',
                          'RETURNING id AS "leagueId", status AS "leagueStatus"')
        return super().execute(text(sql), params)


class DraftControlAuthorizationTests(unittest.TestCase):
    actions = ('start', 'pause', 'resume', 'finalize', 'order')

    def setUp(self):
        self.fixture = live_fixture.LivePickAuthorizationTests()
        self.fixture.database_type = ControlDatabase
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.db, self.model, self.client = self.fixture.db, self.fixture.model, self.fixture.client
        self.headers, self.emit = self.fixture.headers, self.fixture.emit
        self.db.connection.executescript('''
            ALTER TABLE "League" ADD COLUMN sport INTEGER DEFAULT 1;
            ALTER TABLE "League" ADD COLUMN status TEXT DEFAULT 'Pre-Draft';
            ALTER TABLE "League" ADD COLUMN "updatedAt" TEXT;
            CREATE TABLE "SportSeason" ("sportId" INTEGER, "seasonYear" INTEGER, "seasonStart" TEXT, "seasonEnd" TEXT);
            INSERT INTO "SportSeason" VALUES (1, 2026, '2026-11-01', '2027-03-31');
            CREATE UNIQUE INDEX draft_turn_unique ON "DraftTurn" ("leagueId", "overallPickNumber");
        ''')

    def prepare(self, action, league_id=10):
        if action in ('start', 'order'):
            for table in ('DraftState', 'DraftPick', 'DraftTurn'):
                self.db.connection.execute(f'DELETE FROM "{table}" WHERE "leagueId" = ?', (league_id,))
        else:
            self.db.connection.execute('''INSERT INTO "DraftState"
                ("leagueId", status, "currentOverallPickNumber", "currentMemberId", "updatedAt")
                VALUES (?, ?, ?, ?, 'old')
                ON CONFLICT ("leagueId") DO UPDATE SET status = excluded.status''',
                (league_id, 'paused' if action == 'resume' else 'live',
                 2 if league_id == 10 else 1, 12 if league_id == 10 else 21))
        self.db.connection.commit()
        self.emit.reset_mock()

    def body(self, action, league_id=10, actor=1):
        if action == 'order':
            return {'memberIdsInOrder': ['12', '11'] if league_id == 10 else ['21']}
        result = {'leagueId': str(league_id)}
        if action == 'finalize':
            result['actingUserId'] = str(actor)
        return result

    def invoke(self, action, subject=identities.ALICE, league_id=10, body=None, headers=None):
        payload = self.body(action, league_id, 2 if subject == identities.BOB else 1) if body is None else body
        kwargs = {'json': payload, 'headers': self.headers(subject) if headers is None else headers}
        if action == 'order':
            return self.client.put(f'/api/league/{league_id}/draft/order', **kwargs)
        return self.client.post(f'/api/draft/{action}', **kwargs)

    def state(self):
        return {table: [dict(row) for row in self.db.connection.execute(f'SELECT * FROM "{table}" ORDER BY 1')]
                for table in ('League', 'LeagueMember', 'DraftState', 'DraftTurn', 'DraftPick', 'LeagueTeamSlot')}

    def test_own_commissioners_keep_success_state_response_and_event_contracts(self):
        for subject, league_id in ((identities.ALICE, 10), (identities.BOB, 20)):
            for action in self.actions:
                with self.subTest(subject=subject, action=action):
                    self.prepare(action, league_id)
                    response = self.invoke(action, subject, league_id)
                    self.assertEqual(response.status_code, 200, response.json)
                    if action == 'order':
                        self.assertEqual(set(response.json), {'members'})
                        self.assertEqual([row['memberId'] for row in response.json['members']], [12, 11] if league_id == 10 else [21])
                        self.emit.assert_not_called()
                    else:
                        status = 'paused' if action == 'pause' else 'complete' if action == 'finalize' else 'live'
                        self.assertEqual(response.json['state']['status'], status)
                        self.assertEqual(response.json['leagueId'], league_id)
                        if action == 'finalize':
                            self.assertTrue(response.json['draftComplete'])
                            self.assertEqual(response.json['leagueStatus'], 'Post-Draft')
                        else:
                            self.assertEqual(set(response.json), {'leagueId', 'draftSettings', 'serverNow', 'state', 'members', 'picks', 'onDeck', 'inTheHole'})
                        self.emit.assert_called_once()
                        args, kwargs = self.emit.call_args
                        self.assertEqual(args[0], 'draft:updated')
                        self.assertEqual(args[1]['type'], action)
                        self.assertEqual(args[1]['snapshot']['leagueId'], league_id)
                        self.assertEqual(kwargs, {'room': f'draft:{league_id}'})

    def test_members_nonmembers_and_foreign_commissioners_cannot_control(self):
        for action in self.actions:
            for subject, league_id in ((identities.BOB, 10), (identities.OUTSIDER, 10), (identities.ALICE, 20)):
                with self.subTest(action=action, subject=subject):
                    self.prepare(action, league_id)
                    before = self.state()
                    response = self.invoke(action, subject, league_id)
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(self.state(), before)
                    self.emit.assert_not_called()

    def test_forged_actor_headers_and_job_flags_do_not_supply_authority(self):
        for action in self.actions:
            with self.subTest(action=action):
                self.prepare(action)
                before = self.state()
                body = dict(self.body(action), actingUserId=1, userId=1, trustedJob=True, sub=identities.ALICE)
                headers = self.headers(identities.BOB)
                headers.update({'X-User-Id': '1', 'X-Role': 'commissioner'})
                response = self.invoke(action, body=body, headers=headers)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.state(), before)
                self.emit.assert_not_called()

    def test_auth_and_missing_or_ambiguous_application_identity_deny_all_controls(self):
        for action in self.actions:
            self.prepare(action)
            for headers, status in (({}, 401), (self.headers(exp=1), 401),
                                    (self.headers(''), 401), (self.headers(identities.MISSING), 403)):
                with self.subTest(action=action, status=status):
                    before = self.state()
                    response = self.invoke(action, headers=headers)
                    self.assertEqual(response.status_code, status)
                    self.assertIn('error', response.json)
                    self.assertEqual(self.state(), before)
                    self.emit.assert_not_called()
        self.db.connection.executescript('''
            ALTER TABLE "User" RENAME TO old_user;
            CREATE TABLE "User" AS SELECT * FROM old_user;
            INSERT INTO "User" SELECT 4, uuid, 'duplicate@example.test', 'Duplicate', "createdAt" FROM old_user WHERE id = 1;
        ''')
        for action in self.actions:
            with self.subTest(ambiguous=action):
                before = self.state()
                response = self.invoke(action)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json, {'error': 'application_identity_ambiguous'})
                self.assertEqual(self.state(), before)
                self.emit.assert_not_called()

    def test_invalid_bodies_ids_and_actor_assertions_are_json_client_errors(self):
        for action in self.actions:
            for body in ([], 'text', {}, dict(self.body(action), actingUserId=True),
                         {'memberIdsInOrder': [True]} if action == 'order' else dict(self.body(action), leagueId=10.5)):
                with self.subTest(action=action, body=body):
                    before = self.state()
                    response = self.invoke(action, body=body)
                    self.assertEqual(response.status_code, 400)
                    self.assertIsInstance(response.json.get('message'), str)
                    self.assertEqual(self.state(), before)
                    self.emit.assert_not_called()
        self.assertEqual(self.invoke('finalize', body={'leagueId': 10}).status_code, 400)

    def test_order_uses_url_league_and_existing_foreign_member_rejection(self):
        self.prepare('order')
        before = self.state()
        response = self.invoke('order', body={'leagueId': 20, 'memberIdsInOrder': [21, 12]})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.state(), before)
        response = self.invoke('order', body={'leagueId': 20, 'memberIdsInOrder': [12, 11]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([m['memberId'] for m in response.json['members']], [12, 11])
        self.assertEqual([m for m in self.state()['LeagueMember'] if m['leagueId'] == 20],
                         [m for m in before['LeagueMember'] if m['leagueId'] == 20])
        self.emit.assert_not_called()

    def test_late_commissioner_change_rolls_back_every_control_before_commit(self):
        for action in self.actions:
            with self.subTest(action=action):
                self.prepare(action)
                before = self.state()
                checks = 0
                def revoke(sql):
                    nonlocal checks
                    if 'SELECT commissioner' in sql:
                        checks += 1
                        if checks == 2:
                            self.db.before_query = None
                            self.db.connection.execute('UPDATE "League" SET commissioner = 2 WHERE id = 10')
                self.db.before_query = revoke
                response = self.invoke(action)
                self.db.before_query = None
                self.assertEqual(response.status_code, 403)
                self.assertEqual(self.state(), before)
                self.emit.assert_not_called()

    def test_finalize_failure_after_state_write_rolls_back_state_and_league(self):
        before = self.state()
        def fail(sql):
            if 'UPDATE "League"' in sql:
                raise RuntimeError('synthetic finalization failure')
        self.db.before_query = fail
        response = self.invoke('finalize')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.state(), before)
        self.emit.assert_not_called()

    def test_commissioner_control_does_not_require_personal_membership(self):
        self.db.connection.execute('DELETE FROM "LeagueMember" WHERE id = 11')
        response = self.invoke('pause')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['state']['status'], 'paused')
        self.emit.assert_called_once()

    def test_trusted_calls_stay_outside_http_and_force_finalize_still_checks_actor(self):
        self.prepare('start')
        self.assertEqual(self.model.start_draft(10)['state']['status'], 'live')
        self.assertEqual(self.model.pause_draft(10)['state']['status'], 'paused')
        self.assertEqual(self.model.resume_draft(10)['state']['status'], 'live')
        with self.assertRaises(PermissionError):
            self.model.force_finalize_draft(10, 2)
        with self.assertRaises((PermissionError, TypeError)):
            self.model.force_finalize_draft(10, None)
        self.assertTrue(self.model.force_finalize_draft(10, 1)['draftComplete'])
        self.prepare('order')
        self.assertEqual([m['memberId'] for m in self.model.set_draft_order(10, [12, 11])['members']], [12, 11])
        self.emit.assert_not_called()
