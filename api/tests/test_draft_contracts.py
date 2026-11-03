"""K6/J3 transport slice: observable HTTP and room-event contracts, not a live draft."""
import datetime as dt
import sys
import time
import jwt
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from endpoints.draft.draftEndpoints import DraftEndpoints
from endpoints.draft.routes import setup_routes
from socketioInstance import socketio
from authMiddleware import install_auth_middleware
from supabaseAuth import ISSUER, SUPABASE_JWT_SECRET
from test_profile_regression import ALICE, ProfileDatabase


class DraftContractTests(unittest.TestCase):
    def setUp(self):
        # Only the persistence/state model is substituted; handlers, JSON
        # serialization and broadcast routing execute their real code.
        self.model = Mock()
        app = Flask(__name__)
        app.config["TESTING"] = True
        self.db = ProfileDatabase()
        self.addCleanup(self.db.connection.close)
        install_auth_middleware(app)
        with patch('endpoints.draft.draftEndpoints.DraftPickService', return_value=self.model), \
             patch('endpoints.draft.draftEndpoints.DraftSnapshotService', return_value=self.model):
            setup_routes(app, self.db)
        self.client = app.test_client()
        token = jwt.encode(dict(sub=ALICE, aud='authenticated', iss=ISSUER,
                                exp=int(time.time()) + 600), SUPABASE_JWT_SECRET, algorithm='HS256')
        self.client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        self.body = {"leagueId": 7, "memberId": 11, "sportTeamId": 21}
        self.emitter = patch.object(socketio, 'emit')
        self.emitted = self.emitter.start()
        self.addCleanup(self.emitter.stop)

    def test_committed_pick_returns_created_json_and_matching_league_event(self):
        self.model.pick_live.return_value = {
            "id": 31, "leagueId": 7, "memberId": 11, "sportTeamId": 21,
            "overallPickNumber": 1, "roundNumber": 1, "pickInRound": 1,
            "createdAt": dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
        }
        self.model.snapshot_for_job.return_value = {
            "leagueId": 7, "state": {"currentOverallPickNumber": 2},
        }
        response = self.client.post('/api/draft/pick', json=self.body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json, {
            "id": 31, "leagueId": 7, "memberId": 11, "sportTeamId": 21,
            "overallPickNumber": 1, "roundNumber": 1, "pickInRound": 1,
            "createdAt": "2026-01-01T00:00:00+00:00",
        })
        self.emitted.assert_called_once_with('draft:updated', {
            "type": "pick", "pick": response.json,
            "snapshot": {"leagueId": 7, "state": {"currentOverallPickNumber": 2}},
        }, room='draft:7')

    def test_rejected_or_conflicting_pick_never_emits_success(self):
        for error, status in [
            (ValueError("Not your turn"), 409),
            (ValueError("Pick expired"), 409),
            (ValueError("Conference limit reached"), 400),
            (IntegrityError("synthetic statement", {}, Exception("synthetic unique violation")), 409),
        ]:
            with self.subTest(reason=type(error).__name__, status=status):
                self.model.pick_live.side_effect = error
                response = self.client.post('/api/draft/pick', json=self.body)
                self.assertEqual(response.status_code, status)
                self.assertIsInstance(response.json.get("message"), str)
                self.assertNotIn("pick", response.json)
                self.emitted.assert_not_called()

    def test_missing_pick_input_is_a_client_error_without_success_event(self):
        response = self.client.post('/api/draft/pick', json={"leagueId": 7})
        self.assertEqual(response.status_code, 400)
        self.assertIn("memberId", response.json["message"])
        self.assertIn("sportTeamId", response.json["message"])
        self.emitted.assert_not_called()
        self.model.pick_live.assert_not_called()
