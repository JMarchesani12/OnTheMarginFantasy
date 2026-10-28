from flask import request, jsonify, g
from .userModel import UserModel
from authenticatedPrincipal import PrincipalResolutionError, resolve_authenticated_principal, verified_request_subject

class UserEndpoints:
    def __init__(self, db_engine):
        self.userModel = UserModel(db_engine)
        self.db_engine = db_engine

    # GET /api/user/<user_id>
    def get_user(self, user_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            if user_id != principal.user_id:
                return jsonify({"message": "User not found"}), 404
            user = self.userModel.get_user_by_id(principal.user_id)
            return jsonify(user), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except ValueError as e:
            return jsonify({"message": str(e)}), 404
        except Exception:
            return jsonify({"message": "Failed to fetch user"}), 500
        
    # GET /api/user/byUuid/<uuid> -- private bootstrap lookup
    def get_user_by_uuid(self, uuid: str):
        try:
            subject = verified_request_subject()
            if uuid != subject:
                return jsonify({"message": "User not found"}), 404
            principal = resolve_authenticated_principal(self.db_engine)
            user = self.userModel.get_user_by_id(principal.user_id)
            return jsonify(user), 200
        except PrincipalResolutionError as e:
            # Only an authenticated subject's absent profile means "create it".
            if e.code == 'application_identity_not_found':
                return jsonify({"message": "User not found"}), 404
            return jsonify({"error": e.code}), e.status_code
        except ValueError as e:
            return jsonify({"message": str(e)}), 404
        except Exception:
            return jsonify({"message": "Failed to fetch user"}), 500

    # POST /api/user -- identity/email come exclusively from verified claims.
    def create_user(self):
        try:
            subject = verified_request_subject()
            email = g.user.get('email')
            if not isinstance(email, str) or not email.strip():
                return jsonify({"error": "authenticated_email_required"}), 403
            email = email.strip()
            data = request.get_json(silent=True)
            if not isinstance(data, dict):
                return jsonify({"message": "Expected a JSON object"}), 400
            # Matching legacy fields remain accepted; conflicting identity fails.
            if (('uuid' in data and data['uuid'] != subject) or
                    ('email' in data and data['email'] != email)):
                return jsonify({"error": "profile_identity_mismatch"}), 403
            display_name = data.get('displayName')
            if display_name is not None and not isinstance(display_name, str):
                return jsonify({"message": "displayName must be a string"}), 400

            try:
                resolve_authenticated_principal(self.db_engine)
            except PrincipalResolutionError as e:
                if e.code != 'application_identity_not_found':
                    raise
            else:
                return jsonify({"message": "User already exists"}), 409

            user = self.userModel.create_user(
                email=email, display_name=display_name, uuid=subject,
            )
            return jsonify(user), 201
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except ValueError:
            return jsonify({"message": "User creation failed"}), 400
        except Exception:
            return jsonify({"message": "Failed to create user"}), 500

    # PATCH /api/user/<user_id>
    def update_user(self, user_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            if user_id != principal.user_id:
                return jsonify({"message": "User not found"}), 404
            body = request.get_json(force=True) or {}
            updated = self.userModel.update_user(principal.user_id, body)
            return jsonify(updated), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to update user"}), 500