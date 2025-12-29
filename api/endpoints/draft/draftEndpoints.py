# endpoints/draft/draftEndpoints.py
from flask import request, jsonify
from endpoints.draft.draftModel import DraftModel

class DraftEndpoints:
    def __init__(self, db_engine):
        self.draftModel = DraftModel(db_engine)

    # POST /api/draft/pick
    # {
    #   "leagueId": 1,
    #   "memberId": 7,
    #   "sportTeamId": 42
    # }
    def create_pick(self):
        data = request.get_json() or {}

        required = ["leagueId", "memberId", "sportTeamId"]
        missing = [k for k in required if k not in data]
        if missing:
            return jsonify({"message": f"Missing fields: {', '.join(missing)}"}), 400

        league_id = int(data["leagueId"])
        member_id = int(data["memberId"])
        sport_team_id = int(data["sportTeamId"])
        week_number = int(data.get("weekNumber", 1))

        try:
            draft_pick = self.draftModel.create_draft_pick(
                league_id=league_id,
                member_id=member_id,
                sport_team_id=sport_team_id,
                acquired_week=week_number,
            )
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            # log e if you have logging
            return jsonify({"message": "Failed to create draft pick"}), 500

        return jsonify(draft_pick), 201

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
        try:
            body = request.get_json(force=True) or {}
            ids = body.get("memberIdsInOrder")

            if not isinstance(ids, list) or not ids:
                return jsonify({"message": "memberIdsInOrder must be a non-empty array"}), 400

            result = self.draftModel.set_draft_order(
                league_id=league_id,
                member_ids_in_order=[int(x) for x in ids],
            )
            return jsonify(result), 200

        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            return jsonify({"message": e}), 500
            return jsonify({"message": "Failed to set draft order"}), 500