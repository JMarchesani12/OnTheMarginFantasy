from flask import request, jsonify
from .leagueModel import LeagueModel

class LeagueEndpoints:
    def __init__(self, db_engine):
        self.leagueModel = LeagueModel(db_engine)

    def create_league(self):
        data = request.get_json() or {}

        required = ["name", "sport", "numPlayers", "status", "settings", "draftDate", "commissioner"]
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
            "commissioner": data["commissioner"]
        }

        # Insert league + optionally initial member
        created = self.leagueModel.create_league(league=league_data)

        return jsonify(created), 201
    
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