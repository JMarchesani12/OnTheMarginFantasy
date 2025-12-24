# endpoints/roster/rosterEndpoints.py
from flask import request, jsonify
from .rosterModel import RosterModel

class RosterEndpoints:
    def __init__(self, db_engine):
        self.rosterModel = RosterModel(db_engine)

    # POST /api/roster/memberTeams
    # { "leagueId": 1, "memberId": 7, "weekNumber": 1 }
    def get_member_teams(self):
        data = request.get_json() or {}
        league_id = data.get("leagueId")
        member_id = data.get("memberId")
        week_number = data.get("weekNumber")

        if league_id is None or member_id is None or week_number is None:
            return jsonify({"message": "leagueId, memberId, weekNumber are required"}), 400

        teams = self.rosterModel.get_member_teams_for_week(
            int(league_id),
            int(member_id),
            int(week_number),
        )
        return jsonify(teams)
    
    # POST /api/roster/availableTeams
    # { "leagueId": 1, "weekNumber": 1 }
    def get_available_teams(self):
        data = request.get_json() or {}
        league_id = data.get("leagueId")
        week_number = data.get("weekNumber")

        if league_id is None or week_number is None:
            return jsonify({"message": "leagueId and weekNumber are required"}), 400

        teams = self.rosterModel.get_available_teams_for_week(
            int(league_id),
            int(week_number),
        )
        return jsonify(teams)
