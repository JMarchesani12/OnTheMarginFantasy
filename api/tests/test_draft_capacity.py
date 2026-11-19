"""Capacity rules: all conferences optional, every round offers equal pick counts."""
import unittest
from utils.draft_capacity import calculate_rounds


class DraftCapacityTests(unittest.TestCase):
    def conferences(self, *values):
        return [dict(sportConferenceId=i, teamsInConference=teams, maxTeamsPerOwner=cap)
                for i, (teams, cap) in enumerate(values, 1)]

    def test_twelve_owners_example_counts_only_usable_teams(self):
        self.assertEqual(calculate_rounds(12, 10, self.conferences((16, 2), (10, 1), (14, 1), (8, 1))), 3)

    def test_extra_owner_does_not_automatically_remove_round(self):
        conferences = self.conferences((16, 2), (10, 1), (14, 1), (8, 1))
        self.assertEqual(calculate_rounds(10, 10, conferences), 4)
        self.assertEqual(calculate_rounds(11, 10, conferences), 4)
        self.assertEqual(calculate_rounds(12, 10, conferences), 3)

    def test_sport_maximum_and_conference_caps_are_ceilings(self):
        self.assertEqual(calculate_rounds(2, 3, self.conferences((100, 2), (100, 2))), 3)
        self.assertEqual(calculate_rounds(2, 10, self.conferences((100, 1), (100, 2))), 3)

    def test_not_enough_capacity_is_zero_not_an_invented_round(self):
        self.assertEqual(calculate_rounds(12, 10, self.conferences((5, 1), (6, 2))), 0)
        self.assertEqual(calculate_rounds(1, 10, []), 0)

    def test_zero_cap_contributes_no_capacity(self):
        self.assertEqual(calculate_rounds(2, 10, self.conferences((5, 0), (10, 2))), 2)

    def test_invalid_configuration_fails_closed(self):
        for players, maximum, conferences in ((0, 10, []), (2, None, []),
                (2, 10, self.conferences((5, None))), (2, 10, self.conferences((5, -1)))):
            with self.subTest(players=players, maximum=maximum, conferences=conferences):
                with self.assertRaises(ValueError): calculate_rounds(players, maximum, conferences)


class DraftCapacityIntegrationTests(unittest.TestCase):
    def fixture(self, module, class_name):
        from importlib import import_module
        fixture = getattr(import_module(module), class_name)()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_creation_uses_capacity_and_preserves_other_settings(self):
        from endpoints.league.administration.service import LeagueAdminService
        from actors import UserActor
        base = self.fixture('test_league_creation_authorization', 'LeagueCreationAuthorizationTests')
        row = LeagueAdminService(base.db).create(UserActor(1, 'alice'), base.payload(), lambda *a, **kw: None)
        self.assertEqual(row['settings']['draft']['numberOfRounds'], 8)
        self.assertEqual(row['settings']['timezone'], 'UTC')

    def test_removing_owner_recalculates_from_actual_count(self):
        from endpoints.league.members.service import MemberService
        from actors import UserActor
        import json
        base = self.fixture('test_member_removal_authorization', 'MemberRemovalAuthorizationTests')
        base.db.connection.execute('UPDATE "League" SET "numPlayers"=99')
        base.db.connection.execute('UPDATE "SportConference" SET "maxTeamsPerOwner"=2')
        base.db.connection.commit()
        MemberService(base.db).remove(UserActor(1, 'alice'), 10, 13)
        row = base.db.connection.execute('SELECT "numPlayers",settings FROM "League" WHERE id=10').fetchone()
        self.assertEqual(row['numPlayers'], 2)
        self.assertEqual(json.loads(row['settings'])['draft']['numberOfRounds'], 2)

    def test_start_recalculates_stale_rounds_from_effective_season(self):
        from endpoints.draft.control_service import DraftControlService
        base = self.fixture('test_draft_control_authorization', 'DraftControlAuthorizationTests')
        base.prepare('start')
        # Four teams in a cap-2 conference initially permit two rounds. Move
        # two teams to a cap-zero conference this season, overriding fallback.
        base.db.connection.executescript('''
            INSERT INTO "SportConference" VALUES (502,1,402,0);
            UPDATE "ConferenceMembership" SET "seasonYear"=NULL WHERE "sportTeamId" IN (90001,90002);
            INSERT INTO "ConferenceMembership" VALUES (90001,1,2026,502),(90002,1,2026,502);
        ''')
        result = DraftControlService(base.db).start_for_job(10)
        self.assertEqual(result['draftSettings']['numberOfRounds'], 1)
        self.assertEqual(base.db.connection.execute('SELECT COUNT(*) FROM "DraftTurn" WHERE "leagueId"=10').fetchone()[0], 2)

    def test_start_rejects_no_full_round_atomically(self):
        from endpoints.draft.control_service import DraftControlService
        base = self.fixture('test_draft_control_authorization', 'DraftControlAuthorizationTests')
        base.prepare('start')
        base.db.connection.execute('DELETE FROM "ConferenceMembership" WHERE "sportTeamId"<>101')
        base.db.connection.commit()
        before = base.state()
        with self.assertRaisesRegex(ValueError, 'capacity|round'):
            DraftControlService(base.db).start_for_job(10)
        self.assertEqual(base.state(), before)

    def test_refresh_does_not_resize_live_draft(self):
        from utils.draft_capacity import refresh_draft_capacity
        base = self.fixture('test_draft_control_authorization', 'DraftControlAuthorizationTests')
        base.prepare('pause')
        before = base.state()
        with base.db.begin() as conn:
            self.assertIsNone(refresh_draft_capacity(conn, 10))
        self.assertEqual(base.state(), before)
