# endpoints/league/transactionEndpoints.py

from flask import request, jsonify
from sqlalchemy import text
from .transactionModel import TransactionModel


class TransactionEndpoints:
    def __init__(self, db_engine):
        self.transactionModel = TransactionModel(db_engine)

    # POST /api/league/<league_id>/week/<week_id>/trade/propose
    # {
    #     "fromMemberId": 12,
    #     "toMemberId": 34,
    #     "fromTeamIds": [101, 102],
    #     "toTeamIds": [205]
    # }
    def propose_trade(self, league_id: int, week_id: int):
        body = request.get_json(force=True) or {}

        required = ["fromMemberId", "toMemberId", "fromTeamIds", "toTeamIds"]
        missing = [k for k in required if k not in body]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

        try:
            result = self.transactionModel.propose_trade(
                league_id=league_id,
                week_id=week_id,
                from_member_id=int(body["fromMemberId"]),
                to_member_id=int(body["toMemberId"]),
                from_team_ids=[int(x) for x in body["fromTeamIds"]],
                to_team_ids=[int(x) for x in body["toTeamIds"]],
            )
            return jsonify(result), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    # POST /api/league/<league_id>/transaction/<transaction_id>/trade/respond
    # body: { action: "ACCEPT"|"REJECT", responderMemberId, rejectReason? }
    def respond_trade(self, league_id: int, transaction_id: int):
        body = request.get_json(force=True) or {}

        required = ["action", "responderMemberId"]
        missing = [k for k in required if k not in body]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

        try:
            result = self.transactionModel.respond_to_trade(
                transaction_id=int(transaction_id),
                action=str(body["action"]),
                responder_member_id=int(body["responderMemberId"]),
                reject_reason=body.get("rejectReason"),
            )
            return jsonify(result), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    # POST /api/league/<league_id>/transaction/<transaction_id>/trade/cancel
    # body: { requesterMemberId }
    def cancel_trade(self, league_id: int, transaction_id: int):
        body = request.get_json(force=True) or {}
        if "requesterMemberId" not in body:
            return jsonify({"error": "Missing field: requesterMemberId"}), 400

        try:
            result = self.transactionModel.cancel_trade_proposal(
                transaction_id=int(transaction_id),
                requester_member_id=int(body["requesterMemberId"]),
            )
            return jsonify(result), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

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
        data = request.get_json() or {}

        week_id = data.get("weekId")
        week_number = data.get("weekNumber")
        member_id = data.get("memberId")

        if week_id is None or week_number is None or member_id is None:
            return jsonify({"message": "weekId, weekNumber and memberId are required"}), 400

        try:
            week_id = int(week_id)
            week_number = int(week_number)
            member_id = int(member_id)
        except (TypeError, ValueError):
            return jsonify({"message": "weekId, weekNumber and memberId must be integers"}), 400

        add_team_id = data.get("addTeamId")
        drop_team_id = data.get("dropTeamId")

        if add_team_id is None and drop_team_id is None:
            return jsonify({"message": "addTeamId or dropTeamId is required"}), 400

        try:
            if add_team_id is not None:
                add_team_id = int(add_team_id)
            if drop_team_id is not None:
                drop_team_id = int(drop_team_id)
        except (TypeError, ValueError):
            return jsonify({"message": "addTeamId and dropTeamId must be integers"}), 400

        try:
            result = self.transactionModel.free_agency_add_drop(
                league_id=int(leagueId),
                week_id=week_id,
                week_number=week_number,
                member_id=member_id,
                add_team_id=add_team_id,
                drop_team_id=drop_team_id,
            )
        except TransactionModel.SwapLimitExceeded as e:
            return jsonify({"message": "Max swaps reached", "details": str(e)}), 400
        except ValueError as e:
            return jsonify({"message": "Free agency move rejected", "details": str(e)}), 400
        except Exception as e:
            return jsonify(
                {"message": "Failed to process free agency move", "details": str(e)}
            ), 500

        return jsonify(result), 200
    
    # POST /api/league/<leagueId>/week/<weekId>/lock
    def lock_week(self, leagueId, weekId):
        league_id = int(leagueId)
        week_id = int(weekId)

        try:
            # Will raise ValueError if any roster is illegal
            self.transactionModel.assert_week_rosters_valid(league_id, week_id)
        except ValueError as e:
            return jsonify(
                {
                    "message": "Cannot lock week; roster violations present",
                    "details": str(e),
                }
            ), 400

        # If everything is valid, lock the week
        sql = text(
            """
            UPDATE "Week"
            SET "isLocked" = true
            WHERE id = :week_id
              AND "leagueId" = :league_id
            """
        )

        with self.db.begin() as conn:
            conn.execute(sql, {"week_id": week_id, "league_id": league_id})

        return jsonify(
            {"message": "Week locked successfully", "leagueId": league_id, "weekId": week_id}
        ), 200

    from flask import request, jsonify

    # POST /api/league/<league_id>/transactions/trades/open
    # body: { "memberId": 123 }
    def get_open_trade_transactions(self, league_id: int):
        body = request.get_json(force=True) or {}
        if "memberId" not in body:
            return jsonify({"error": "memberId is required"}), 400

        try:
            member_id = int(body["memberId"])
            result = self.transactionModel.get_open_trade_transactions_for_member(
                league_id=league_id,
                member_id=member_id,
            )
            return jsonify(result), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    # POST /api/league/<int:league_id>/transaction/<int:transaction_id>/trade/veto
    # body: { "memberId": 123 }  // LeagueMember.id
    def veto_trade(self, league_id: int, transaction_id: int):
        body = request.get_json(force=True) or {}
        if "memberId" not in body:
            return jsonify({"error": "memberId is required"}), 400

        try:
            result = self.transactionModel.veto_trade(
                transaction_id=int(transaction_id),
                league_member_id=int(body["memberId"]),
            )
            return jsonify(result), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        
    # POST /api/league/<int:league_id>/transaction/<int:transaction_id>/trade/apply
    # body: {}
    def apply_trade(self, league_id: int, transaction_id: int):
        try:
            result = self.transactionModel.apply_trade(
                transaction_id=int(transaction_id)
            )
            return jsonify(result), 200
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
