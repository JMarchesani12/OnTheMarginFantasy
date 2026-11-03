# endpoints/league/transactionEndpoints.py

from flask import request, jsonify
from .workflow_service import TransactionWorkflowService
from .service import TransactionService
from .contracts import TransactionAccessDenied
from actors import UserActor
from authenticatedPrincipal import PrincipalResolutionError, resolve_authenticated_principal
from utils.requestValidation import integer_field, integer_list_field


class TransactionEndpoints:
    def __init__(self, db_engine):
        self.workflow_service = TransactionWorkflowService(db_engine)
        self.db_engine = db_engine
        self.transaction_service = TransactionService(db_engine)

    # POST /api/league/<league_id>/week/<week_id>/trade/propose
    # {
    #     "fromMemberId": 12,
    #     "toMemberId": 34,
    #     "fromTeamIds": [101, 102],
    #     "toTeamIds": [205]
    # }
    def propose_trade(self, league_id: int, week_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({"error": "Request body must be a JSON object"}), 400

            result = self.workflow_service.propose(
                actor=UserActor(principal.user_id, principal.subject),
                league_id=league_id,
                week_id=week_id,
                from_member_id=integer_field(body, "fromMemberId"),
                to_member_id=integer_field(body, "toMemberId"),
                from_team_ids=integer_list_field(body, "fromTeamIds"),
                to_team_ids=integer_list_field(body, "toTeamIds"),
            )
            return jsonify(result), 200
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except PermissionError:
            return jsonify({'message': 'League member not found'}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception:
            return jsonify({'message': 'Failed to propose trade'}), 500

    # POST /api/league/<league_id>/transaction/<transaction_id>/trade/respond
    # body: { action: "ACCEPT"|"REJECT", responderMemberId, rejectReason? }
    def respond_trade(self, league_id: int, transaction_id: int):
        return self._trade_action_response('respond', league_id, transaction_id)

    # POST /api/league/<league_id>/transaction/<transaction_id>/trade/cancel
    # body: { requesterMemberId }
    def cancel_trade(self, league_id: int, transaction_id: int):
        return self._trade_action_response('cancel', league_id, transaction_id)

    def _trade_action_response(self, operation: str, league_id: int, transaction_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({'error': 'Request body must be a JSON object'}), 400
            actor = {'league_id': league_id, 'actor': UserActor(principal.user_id, principal.subject)}
            if operation == 'respond':
                action = body.get('action')
                if not isinstance(action, str):
                    return jsonify({'error': 'action must be a string'}), 400
                result = self.workflow_service.respond(
                    transaction_id=transaction_id,
                    action=action,
                    responder_member_id=integer_field(body, 'responderMemberId'),
                    reject_reason=body.get('rejectReason'),
                    **actor,
                )
            else:
                result = self.workflow_service.cancel(
                    transaction_id=transaction_id,
                    requester_member_id=integer_field(body, 'requesterMemberId'),
                    **actor,
                )
            return jsonify(result), 200
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except PermissionError:
            return jsonify({'message': 'Trade not found'}), 404
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception:
            message = 'Failed to respond to trade' if operation == 'respond' else 'Failed to cancel trade'
            return jsonify({'message': message}), 500

    # POST /api/league/<leagueId>/freeAgency/addDrop
    #
    # Body:
    # {
    #   "weekId": 5,
    #   "weekNumber": 3,
    #   "memberId": 1,
    #   "addTeamId": 301,   # optional
    #   "dropTeamId": 101   # optional
    # }
    def free_agency_add_drop(self, leagueId):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({"message": "Request body must be a JSON object"}), 400

            week_id = integer_field(data, "weekId")
            week_number = integer_field(data, "weekNumber")
            member_id = integer_field(data, "memberId")
            add_team_id = (integer_field(data, "addTeamId")
                           if data.get("addTeamId") is not None else None)
            drop_team_id = (integer_field(data, "dropTeamId")
                            if data.get("dropTeamId") is not None else None)
            if add_team_id is None and drop_team_id is None:
                return jsonify({"message": "addTeamId or dropTeamId is required"}), 400

            result = self.workflow_service.free_agency(
                actor=UserActor(principal.user_id, principal.subject),
                league_id=leagueId,
                week_id=week_id,
                week_number=week_number,
                member_id=member_id,
                add_team_id=add_team_id,
                drop_team_id=drop_team_id,
            )
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except PermissionError:
            return jsonify({'message': 'League member not found'}), 404
        except TransactionWorkflowService.SwapLimitExceeded as e:
            return jsonify({"message": "Max swaps reached", "details": str(e)}), 400
        except ValueError as e:
            return jsonify({"message": "Free agency move rejected", "details": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to process free agency move"}), 500

        return jsonify(result), 200

    # POST /api/league/<leagueId>/week/<weekId>/lock
    def lock_week(self, leagueId, weekId):
        # Historical unregistered helper; no new route or HTTP capability added.
        league_id, week_id = int(leagueId), int(weekId)
        try:
            result = self.workflow_service.lock_week_for_job(league_id, week_id)
        except ValueError as exc:
            return jsonify({'message': 'Cannot lock week; roster violations present', 'details': str(exc)}), 400
        return jsonify(result), 200

    from flask import request, jsonify

    # POST /api/league/<league_id>/transactions/trades/open
    # body: { "memberId": 123 }
    def get_open_trade_transactions(self, league_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({'error': 'Request body must be a JSON object'}), 400
            result = self.workflow_service.open_trades(
                actor=UserActor(principal.user_id, principal.subject),
                league_id=league_id,
                member_id=integer_field(body, 'memberId'),
            )
            return jsonify(result), 200
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except PermissionError:
            return jsonify({'message': 'League member not found'}), 404
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception:
            return jsonify({'error': 'Failed to get open trades'}), 500

    # POST /api/league/<int:league_id>/transaction/<int:transaction_id>/trade/veto
    # body: { "memberId": 123 }  // LeagueMember.id
    def veto_trade(self, league_id: int, transaction_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            body = request.get_json(silent=True)
            if not isinstance(body, dict):
                return jsonify({'error': 'Request body must be a JSON object'}), 400
            result = self.workflow_service.veto(
                actor=UserActor(principal.user_id, principal.subject),
                transaction_id=transaction_id,
                league_member_id=integer_field(body, 'memberId'),
                league_id=league_id,
            )
            return jsonify(result), 200
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except PermissionError:
            return jsonify({'message': 'Trade not found'}), 404
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 400
        except Exception:
            return jsonify({'message': 'Failed to veto trade'}), 500

    # POST /api/league/<int:league_id>/transaction/<int:transaction_id>/trade/apply
    # body: {}
    def apply_trade(self, league_id: int, transaction_id: int):
        # Approved internal-only operation; trusted callers use the service.
        return jsonify({'error': 'http_trade_application_disabled'}), 410

    # GET /api/league/<league_id>/transactions
    def get_transactions_for_league(self, league_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            status = request.args.get("status") or TransactionWorkflowService.STATUS_PENDING
            result = self.transaction_service.list_transactions(
                UserActor(principal.user_id, principal.subject),
                league_id=int(league_id),
                status=status,
            )
            return jsonify(result), 200
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except (PermissionError, TransactionAccessDenied):
            return jsonify({'message': 'League not found'}), 404
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception:
            return jsonify({"error": "Failed to get transactions"}), 500
