from flask import request, jsonify, g
from .service import UserService
from .contracts import ProfileAccessDenied, ProfileNotFound, ProfileUpdateRejected
from .contracts import (ProfileSubject, ProfileAlreadyExists, ProfileIdentityAmbiguous,
                        ProfileCreationRejected)
from actors import UserActor
from authenticatedPrincipal import PrincipalResolutionError, resolve_authenticated_principal, verified_request_subject

class UserEndpoints:
    def __init__(self, db_engine):
        self.db_engine = db_engine
        self.user_service = UserService(db_engine)

    # GET /api/user/<user_id>
    def get_user(self, user_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            user = self.user_service.get_profile(
                UserActor(principal.user_id, principal.subject), user_id,
            )
            return jsonify(user), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except (ValueError, ProfileNotFound, ProfileAccessDenied) as e:
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
            user = self.user_service.get_profile(
                UserActor(principal.user_id, principal.subject), principal.user_id,
            )
            return jsonify(user), 200
        except PrincipalResolutionError as e:
            # Only an authenticated subject's absent profile means "create it".
            if e.code == 'application_identity_not_found':
                return jsonify({"message": "User not found"}), 404
            return jsonify({"error": e.code}), e.status_code
        except (ValueError, ProfileNotFound, ProfileAccessDenied) as e:
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

            user = self.user_service.create_profile(
                ProfileSubject(subject, email), display_name,
            )
            return jsonify(user), 201
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except ProfileAlreadyExists:
            return jsonify({"message": "User already exists"}), 409
        except ProfileIdentityAmbiguous as e:
            return jsonify({"error": e.code}), 403
        except (ValueError, ProfileCreationRejected):
            return jsonify({"message": "User creation failed"}), 400
        except Exception:
            return jsonify({"message": "Failed to create user"}), 500

    # PATCH /api/user/<user_id>
    def update_user(self, user_id: int):
        try:
            principal = resolve_authenticated_principal(self.db_engine)
            actor = UserActor(principal.user_id, principal.subject)
            # Preserve concealed foreign-target denial before JSON parsing.
            self.user_service.require_profile_owner(actor, user_id)
            body = request.get_json(force=True) or {}
            updated = self.user_service.update_profile(actor, user_id, body)
            return jsonify(updated), 200
        except PrincipalResolutionError as e:
            return jsonify({"error": e.code}), e.status_code
        except ProfileAccessDenied as e:
            return jsonify({"message": str(e)}), 404
        except (ValueError, ProfileNotFound, ProfileUpdateRejected) as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to update user"}), 500