from flask import request, jsonify
from .userModel import UserModel

class UserEndpoints:
    def __init__(self, db_engine):
        self.userModel = UserModel(db_engine)

    # POST /api/user
    # {
    #   "email": "user@example.com",
    #   "displayName": "Haylee",          // optional
    #   "uuid": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" // optional (must exist in auth.users if provided)
    # }
    def create_user(self):
        data = request.get_json() or {}

        if "email" not in data or not data["email"]:
            return jsonify({"message": "Missing field: email"}), 400

        email = str(data["email"]).strip()
        display_name = data.get("displayName")
        uuid = data.get("uuid")

        try:
            user = self.userModel.create_user(
                email=email,
                display_name=display_name,
                uuid=uuid,
            )
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to create user"}), 500

        return jsonify(user), 201
    
    # PATCH /api/user/<user_id>
    def update_user(self, user_id: int):
        try:
            body = request.get_json(force=True) or {}
            updated = self.userModel.update_user(user_id, body)
            return jsonify(updated), 200
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to update user"}), 500