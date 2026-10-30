# endpoints/draft/draftEndpoints.py
from sqlalchemy.exc import IntegrityError
from flask import request, jsonify
from endpoints.draft.draftBroadcast import broadcast_draft_update
from endpoints.draft.draftModel import DraftModel
from .snapshot_service import DraftSnapshotService
from .control_service import DraftControlService
from actors import UserActor
from utils.jsonSafe import jsonSafe
from authenticatedPrincipal import PrincipalResolutionError, resolve_authenticated_principal

class DraftEndpoints:
    def __init__(self, db_engine):
        self.draftModel = DraftModel(db_engine)
        self.db_engine = db_engine
        self.snapshot_service = DraftSnapshotService(db_engine)
        self.control_service = DraftControlService(db_engine)

    # POST /api/draft/pick
    def create_pick(self):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({'message': 'Request body must be a JSON object'}), 400
            required = ['leagueId', 'memberId', 'sportTeamId']
            missing = [key for key in required if key not in data]
            if missing:
                return jsonify({'message': f"Missing fields: {', '.join(missing)}"}), 400

            def integer(value, field):
                if isinstance(value, bool) or not isinstance(value, (int, str)):
                    raise ValueError(f'{field} must be an integer')
                try:
                    return int(value)
                except ValueError:
                    raise ValueError(f'{field} must be an integer') from None

            league_id = integer(data['leagueId'], 'leagueId')
            member_id = integer(data['memberId'], 'memberId')
            sport_team_id = integer(data['sportTeamId'], 'sportTeamId')
            week_number = integer(data.get('weekNumber', 0), 'weekNumber')
            draft_pick = self.draftModel.create_draft_pick_live(
                league_id=league_id,
                member_id=member_id,
                sport_team_id=sport_team_id,
                acquired_week=week_number,
                acting_user_id=principal.user_id,
            )

            snapshot = self.draftModel.get_draft_state_snapshot(league_id)
            broadcast_draft_update(
                league_id,
                {"type": "pick", "snapshot": snapshot, "pick": draft_pick},
            )
            
            return jsonify(jsonSafe(draft_pick)), 201

        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except PermissionError:
            return jsonify({'message': 'League member not found'}), 404
        except ValueError as e:
            msg = str(e).lower()

            # 409 = request is valid but conflicts with current draft state
            if "not your turn" in msg or "expired" in msg or "conflict" in msg:
                return jsonify({"message": str(e)}), 409

            # 400 = bad request / invalid settings / illegal pick
            return jsonify({"message": str(e)}), 400

        except IntegrityError:
            # in case anything bubbles up from unique constraints
            return jsonify({"message": "Pick conflict (already taken)."}), 409

        except Exception:
            return jsonify({"message": "Failed to create draft pick"}), 500
    
    def start(self):
        return self._draft_control_response('start')

    def pause(self):
        return self._draft_control_response('pause')

    def resume(self):
        return self._draft_control_response('resume')

    def finalize(self):
        return self._draft_control_response('finalize')

    def _draft_control_response(self, action: str, league_id=None):
        failures = {
            'start': 'Failed to start draft', 'pause': 'Failed to pause draft',
            'resume': 'Failed to resume draft', 'finalize': 'Failed to finalize draft',
            'order': 'Failed to set draft order',
        }
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({'message': 'Request body must be a JSON object'}), 400
            if action == 'finalize' and ('leagueId' not in body or 'actingUserId' not in body):
                return jsonify({'message': 'Missing field: leagueId or actingUserId'}), 400

            def integer(value, field):
                if isinstance(value, bool) or not isinstance(value, (int, str)):
                    raise ValueError(f'{field} must be an integer')
                try:
                    return int(value)
                except ValueError:
                    raise ValueError(f'{field} must be an integer') from None

            if action != 'order':
                if 'leagueId' not in body:
                    return jsonify({'message': 'Missing field: leagueId'}), 400
                league_id = integer(body['leagueId'], 'leagueId')
            # An actor field can assert compatibility, never establish identity.
            if 'actingUserId' in body:
                if integer(body['actingUserId'], 'actingUserId') != principal.user_id:
                    return jsonify({'message': 'actingUserId does not match authenticated user'}), 403

            if action == 'order':
                ids = body.get('memberIdsInOrder')
                if not isinstance(ids, list) or not ids:
                    return jsonify({'message': 'memberIdsInOrder must be a non-empty array'}), 400
                result = self.draftModel.set_draft_order(
                    league_id=league_id,
                    member_ids_in_order=[integer(value, 'memberId') for value in ids],
                    acting_user_id=principal.user_id,
                )
            elif action == 'finalize':
                result = self.control_service.finalize(UserActor(principal.user_id, principal.subject), league_id)
                snapshot = self.draftModel.get_draft_state_snapshot(league_id)
                broadcast_draft_update(league_id, {'type': action, 'snapshot': snapshot})
            else:
                method = {
                    'start': self.draftModel.start_draft,
                    'pause': self.draftModel.pause_draft,
                    'resume': self.draftModel.resume_draft,
                }[action]
                result = method(league_id, acting_user_id=principal.user_id)
                broadcast_draft_update(league_id, {'type': action, 'snapshot': result})
            return jsonify(result), 200
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except PermissionError as exc:
            return jsonify({'message': str(exc)}), 403
        except ValueError as exc:
            return jsonify({'message': str(exc)}), 400
        except Exception:
            return jsonify({'message': failures[action]}), 500

    # GET /api/draft/state/<league_id>
    def state(self, league_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            snapshot = self.snapshot_service.snapshot(
                UserActor(principal.user_id, principal.subject), league_id,
            )
            return jsonify(snapshot), 200
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except PermissionError:
            return jsonify({'message': 'League not found'}), 404
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to get draft state"}), 500


    # POST /api/draft/pick-manual
    def create_pick_manual(self):
        """HTTP allocation is disabled; trusted model callers remain separate."""
        return jsonify({'error': 'http_manual_pick_disabled'}), 410

    # GET /api/draft/rounds/<int:sportId>
    def get_rounds(self, sportId):
        try:
            rounds = self.draftModel.get_rounds(sportId=sportId)

            if rounds is None:
                return jsonify({"message": "Sport not found"}), 404

        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            # log e
            return jsonify({"message": "Failed to get rounds"}), 500

        return jsonify({"rounds": rounds}), 200

    # PUT /api/league/<league_id>/draft/order
    def set_draft_order(self, league_id: int):
        return self._draft_control_response('order', league_id)
