"""HTTP scoring adapters; trusted jobs call the transport-independent model."""
from flask import jsonify, request
from authenticatedPrincipal import PrincipalResolutionError, resolve_authenticated_principal
from utils.requestValidation import integer_list_field
from .service import ScoringReadService, ScoringService
from .contracts import ScoringReadDenied
from actors import UserActor


class ScoringEndpoints:
    def __init__(self, db_engine, schedule_model):
        self.db_engine = db_engine
        self.scoring_read_service = ScoringReadService(db_engine)
        self.scoring_service = ScoringService(db_engine, schedule_model)

    def score_week(self, league_id: int, week_number: int):
        # Approved internal-only operation. Middleware still authenticates HTTP.
        return jsonify({'error': 'http_weekly_scoring_disabled'}), 410

    def get_points_awarded_for_weeks(self, league_id: int):
        return self._scoring_read_response(league_id, 'points')

    def compute_end_of_year_season_standings(self, league_id: int):
        return self._scoring_read_response(league_id, 'season')

    def _scoring_read_response(self, league_id: int, view: str):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            if view == 'points':
                payload = request.get_json(silent=True)
                if not isinstance(payload, dict):
                    return jsonify({'message': 'Request body must be a JSON object'}), 400
                weeks = integer_list_field(payload, 'weekNumbers')
                if not weeks:
                    return jsonify({'message': 'weekNumbers must be a non-empty array of integers'}), 400
                result = self.scoring_read_service.get_weekly_points(
                    UserActor(principal.user_id, principal.subject), league_id, weeks,
                )
                return jsonify({'weekNumbers': weeks, 'results': result}), 200
            result = self.scoring_service.get_season_standings(
                UserActor(principal.user_id, principal.subject), league_id,
            )
            return jsonify(result), 200
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except (PermissionError, ScoringReadDenied):
            return jsonify({'message': 'League not found'}), 404
        except ValueError as exc:
            return jsonify({'message': str(exc)}), 400
        except Exception:
            message = 'Failed to get points awarded' if view == 'points' else 'Failed to get standings'
            return jsonify({'message': message}), 500
