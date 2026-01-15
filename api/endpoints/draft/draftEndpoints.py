# endpoints/draft/draftEndpoints.py
from sqlalchemy.exc import IntegrityError
from flask import request, jsonify
from endpoints.draft.draftBroadcast import broadcast_draft_update
from endpoints.draft.draftModel import DraftModel
from utils.jsonSafe import jsonSafe

class DraftEndpoints:
    def __init__(self, db_engine):
        self.draftModel = DraftModel(db_engine)

    # POST /api/draft/pick
    def create_pick(self):
        data = request.get_json() or {}

        required = ["leagueId", "memberId", "sportTeamId"]
        missing = [k for k in required if k not in data]
        if missing:
            return jsonify({"message": f"Missing fields: {', '.join(missing)}"}), 400

        league_id = int(data["leagueId"])
        member_id = int(data["memberId"])
        sport_team_id = int(data["sportTeamId"])
        week_number = int(data.get("weekNumber", 0))

        try:
            draft_pick = self.draftModel.create_draft_pick_live(
                league_id=league_id,
                member_id=member_id,
                sport_team_id=sport_team_id,
                acquired_week=week_number,
            )

            snapshot = self.draftModel.get_draft_state_snapshot(league_id)
            broadcast_draft_update(
                league_id,
                {"type": "pick", "snapshot": snapshot, "pick": draft_pick},
            )
            
            return jsonify(jsonSafe(draft_pick)), 201

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

        except Exception as e:
            print("❌ create_pick error:", repr(e))
            return jsonify({"message": "Failed to create draft pick"}), 500
    
    # POST /api/draft/start { "leagueId": 1 }
    def start(self):
        data = request.get_json() or {}
        if "leagueId" not in data:
            return jsonify({"message": "Missing field: leagueId"}), 400

        league_id = int(data["leagueId"])

        try:
            snapshot = self.draftModel.start_draft(league_id)

            # ✅ broadcast to everyone in the draft room
            broadcast_draft_update(
                league_id,
                {"type": "start", "snapshot": snapshot}
            )

            return jsonify(snapshot), 200

        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to start draft"}), 500

    # POST /api/draft/pause { "leagueId": 1 }
    def pause(self):
        data = request.get_json() or {}
        if "leagueId" not in data:
            return jsonify({"message": "Missing field: leagueId"}), 400
        try:
            result = self.draftModel.pause_draft(int(data["leagueId"]))
            broadcast_draft_update(int(data["leagueId"]), {"type":"pause", "snapshot": result})
            return jsonify(result), 200
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to pause draft"}), 500

    # POST /api/draft/resume { "leagueId": 1 }
    def resume(self):
        data = request.get_json() or {}
        if "leagueId" not in data:
            return jsonify({"message": "Missing field: leagueId"}), 400
        try:
            result = self.draftModel.resume_draft(int(data["leagueId"]))
            broadcast_draft_update(int(data["leagueId"]), {"type":"resume", "snapshot": result})
            return jsonify(result), 200
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            return jsonify({"message": "Failed to resume draft"}), 500

    # GET /api/draft/state/<league_id>
    def state(self, league_id: int):
        try:
            return jsonify(self.draftModel.get_draft_state_snapshot(league_id)), 200
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception as e:
            print(e)
            return jsonify({"message": "Failed to get draft state"}), 500


    # POST /api/draft/pick
    # {
    #   "leagueId": 1,
    #   "memberId": 7,
    #   "sportTeamId": 42
    # }
    def create_pick_manual(self):
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
            return jsonify({"message": "Failed to set draft order"}), 500