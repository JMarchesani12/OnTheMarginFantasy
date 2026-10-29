# endpoints/roster/rosterEndpoints.py
from flask import request, jsonify
from .rosterModel import RosterModel
from utils.requestValidation import integer_field
from authenticatedPrincipal import PrincipalResolutionError, resolve_authenticated_principal

class RosterEndpoints:
    def __init__(self, db_engine):
        self.rosterModel = RosterModel(db_engine)
        self.db_engine = db_engine

    # POST /api/roster/memberTeams
    # { "leagueId": 1, "memberId": 7, "weekNumber": 1 }
    def get_member_teams(self):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({"message": "Request body must be a JSON object"}), 400

            teams = self.rosterModel.get_member_teams_for_week(
                integer_field(data, "leagueId"), integer_field(data, "memberId"),
                integer_field(data, "weekNumber"),
                reader_user_id=principal.user_id,
            )
            return jsonify(teams)
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except PermissionError:
            return jsonify({'message': 'League member not found'}), 404
        except ValueError as exc:
            return jsonify({'message': str(exc)}), 400
        except Exception:
            return jsonify({'message': 'Failed to read member roster'}), 500

    # POST /api/roster/availableTeams
    # { "leagueId": 1, "weekNumber": 1 }
    def get_available_teams(self):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({"message": "Request body must be a JSON object"}), 400
            teams = self.rosterModel.get_available_teams_for_week(
                integer_field(data, "leagueId"), integer_field(data, "weekNumber"),
                reader_user_id=principal.user_id,
            )
            return jsonify(teams)
        except PrincipalResolutionError as exc:
            return jsonify({'error': exc.code}), exc.status_code
        except PermissionError:
            return jsonify({'message': 'League not found'}), 404
        except ValueError as exc:
            return jsonify({'message': str(exc)}), 400
        except Exception:
            return jsonify({'message': 'Failed to read available teams'}), 500
