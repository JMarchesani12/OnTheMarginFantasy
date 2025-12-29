from typing import Any, Dict
from venv import logger
from flask import request, jsonify
from .leagueModel import LeagueModel

class LeagueEndpoints:
    def __init__(self, db_engine):
        self.leagueModel = LeagueModel(db_engine)

    def get_league(self, league_id):

        league = self.leagueModel.get_league(league_id)
        
        if not league:
            return jsonify({"message": "League not found"}), 404

        return jsonify(league), 200

    def create_league(self):
        data = request.get_json() or {}

        required = ["name", "sport", "numPlayers", "status", "settings", "draftDate", "commissioner", "seasonYear", "isDiscoverable"]
        missing = [field for field in required if field not in data]

        if missing:
            return jsonify({"message": f"Missing fields: {', '.join(missing)}"}), 400


        league_data = {
            "name": data["name"],
            "sport": data["sport"],
            "numPlayers": data["numPlayers"],
            "status": data["status"],
            "settings": data["settings"],
            "draftDate": data["draftDate"],
            "commissioner": data["commissioner"],
            "seasonYear": data["seasonYear"],
            "isDiscoverable": data["isDiscoverable"]
        }

        # Insert league + optionally initial member
        created = self.leagueModel.create_league(league=league_data)

        return jsonify(created), 201
    
    def update_league(self, league_id: int):
        try:
            patch: Dict[str, Any] = request.get_json(force=True) or {}

            updated = self.leagueModel.update_league(
                league_id=league_id,
                patch=patch,
            )
            return jsonify(updated), 200

        except PermissionError as e:
            return jsonify({"message": str(e)}), 403
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            # log e
            return jsonify({"message": e}), 500
            return jsonify({"message": "Failed to update league"}), 500
    
    # POST /api/leagues/byUser
    # Body: { "userId": 123, "stage": "all" | "active" | "completed" }
    def get_leagues_by_user(self):
        data = request.get_json() or {}
        user_id = data.get("userId")
        if user_id is None:
            return jsonify({"message": "userId is required"}), 400

        stage = data.get("stage", "all")  # optional

        leagues = self.leagueModel.get_leagues_for_user(int(user_id), stage=stage)
        return jsonify(leagues)
    
    def get_league_members(self, league_id):
        try:
            league_id_int = int(league_id)
        except (TypeError, ValueError):
            return jsonify({"message": "Invalid leagueId"}), 400

        members = self.leagueModel.get_members_for_league(league_id_int)
        return jsonify(members), 200

    def get_league_conferences(self, league_id: int):
        """
        GET /api/league/<league_id>/conferences
        """
        try:
            payload = self.leagueModel.get_league_conferences(int(league_id))
            return jsonify(payload), 200
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            import traceback
            traceback.print_exc()
            return jsonify({"message": "Failed to get league conferences"}), 500
        
    def join_request(self, league_id: int):
        """
        Create a pending join request for a user.
        Body: { "userId": number, "message"?: string }
        """
        try:
            body = request.get_json(force=True) or {}
            user_id = body.get("userId")
            message = body.get("message")

            if not user_id:
                return jsonify({"message": "Missing userId"}), 400

            created = self.leagueModel.create_join_request(league_id=league_id, user_id=int(user_id), message=message)
            return jsonify(created), 201

        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            logger.exception("Failed to create join request")
            return jsonify({"message": "Failed to create join request"}), 500

    def join_requests(self, league_id: int):
        """
        List join requests for a league (commissioner only).

        POST body:
        {
            "actingUserId": number,
            "status": "PENDING" | "APPROVED" | "DENIED" | "CANCELLED" (optional)
        }
        """
        try:
            body = request.get_json(force=True) or {}
            acting_user_id = body.get("actingUserId")
            status = body.get("status")

            if not acting_user_id:
                return jsonify({"message": "Missing actingUserId"}), 400

            self.leagueModel._ensure_commissioner(
                league_id=league_id,
                acting_user_id=int(acting_user_id),
            )

            rows = self.leagueModel.list_join_requests(
                league_id=league_id,
                status=status,
            )
            return jsonify(rows), 200

        except PermissionError as e:
            return jsonify({"message": str(e)}), 403
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            logger.exception("Failed to list join requests")
            return jsonify({"message": "Failed to list join requests"}), 500

    def add_user_to_league(self, league_id: int, request_id: int):
        """
        Approve a pending join request (commissioner only).
        Body: { "actingUserId": number }
        """
        try:
            body = request.get_json(force=True) or {}
            acting_user_id = body.get("actingUserId")
            if not acting_user_id:
                return jsonify({"message": "Missing actingUserId"}), 400

            self.leagueModel._ensure_commissioner(league_id=league_id, acting_user_id=int(acting_user_id))

            result = self.leagueModel.approve_join_request(
                league_id=league_id,
                request_id=request_id,
                acting_user_id=int(acting_user_id),
            )
            return jsonify(result), 200

        except PermissionError as e:
            return jsonify({"message": str(e)}), 403
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            logger.exception("Failed to approve join request")
            return jsonify({"message": "Failed to approve join request"}), 500

    def deny_join(self, league_id: int, request_id: int):
        """
        Deny a pending join request (commissioner only).
        Body: { "actingUserId": number }
        """
        try:
            body = request.get_json(force=True) or {}
            acting_user_id = body.get("actingUserId")
            if not acting_user_id:
                return jsonify({"message": "Missing actingUserId"}), 400

            self.leagueModel._ensure_commissioner(league_id=league_id, acting_user_id=int(acting_user_id))

            updated = self.leagueModel.deny_join_request(
                league_id=league_id,
                request_id=request_id,
                acting_user_id=int(acting_user_id),
            )
            return jsonify(updated), 200

        except PermissionError as e:
            return jsonify({"message": str(e)}), 403
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            logger.exception("Failed to deny join request")
            return jsonify({"message": "Failed to deny join request"}), 500

    def cancel_join(self, league_id: int, request_id: int):
        """
        Cancel your own pending join request.
        Body: { "userId": number }
        """
        try:
            body = request.get_json(force=True) or {}
            user_id = body.get("userId")
            if not user_id:
                return jsonify({"message": "Missing userId"}), 400

            updated = self.leagueModel.cancel_join_request(
                league_id=league_id,
                request_id=request_id,
                user_id=int(user_id),
            )
            return jsonify(updated), 200

        except PermissionError as e:
            return jsonify({"message": str(e)}), 403
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            logger.exception("Failed to cancel join request")
            return jsonify({"message": "Failed to cancel join request"}), 500
        
    # DELETE /api/league/<league_id>/members/<member_id>
    def remove_member(self, league_id: int, member_id: int):
        try:
            body = request.get_json(silent=True) or {}
            acting_user_id = body.get("actingUserId")

            if not acting_user_id:
                return jsonify({"message": "actingUserId is required"}), 400

            # Optional: allow caller to override shifting
            shift = body.get("shiftDraftOrder", True)

            result = self.leagueModel.remove_member_and_shift_draft_order(
                league_id=league_id,
                member_id=member_id,
                acting_user_id=int(acting_user_id),
                shift_draft_order=bool(shift),
            )
            return jsonify(result), 200

        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            # Ideally log e
            return jsonify({"message": "Failed to remove member"}), 500
        
    def search_leagues(self):
        try:
            q = request.args.get("q", "")
            sport_id = request.args.get("sportId")

            limit = int(request.args.get("limit", 20))
            offset = int(request.args.get("offset", 0))

            results = self.leagueModel.search_leagues(
                q=q,
                sport_id=int(sport_id) if sport_id is not None else None,
                limit=limit,
                offset=offset,
            )
            return jsonify(results), 200

        except ValueError:
            return jsonify({"message": "Invalid parameters"}), 400
        except Exception:
            logger.exception("Failed to search leagues")
            return jsonify({"message": "Failed to search leagues"}), 500

    # DELETE /api/league/<league_id>
    def delete_league(self, league_id: int):
        try:
            body = request.get_json(silent=True) or {}
            acting_user_id = body.get("actingUserId")

            if not acting_user_id:
                return jsonify({"message": "actingUserId is required"}), 400

            result = self.leagueModel.delete_league(
                league_id=league_id,
                acting_user_id=int(acting_user_id),
            )
            return jsonify(result), 200

        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to delete league"}), 500
        
    # PATCH /api/league/leagueMember/<member_id>
    def patch_league_member(self, member_id: int):
        try:
            body = request.get_json(force=True) or {}
            updated = self.leagueModel.update_league_member(member_id, body)
            return jsonify(updated), 200
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to update league member"}), 500