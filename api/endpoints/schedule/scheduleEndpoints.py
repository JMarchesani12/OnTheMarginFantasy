# endpoints/schedule/scheduleEndpoints.py

from flask import request, jsonify
from sqlalchemy.engine import Engine
import datetime as dt

from endpoints.schedule.scheduleModel import ScheduleModel


class ScheduleEndpoints:
    def __init__(self, db_engine: Engine, espn_base_url: str):
        self.model = ScheduleModel(db_engine, espn_base_url)

        # POST /api/league/<league_id>/bootstrapSchedule
    #
    # Body:
    # {
    #   "maxTeams": 5                      // OPTIONAL, for testing
    # }
    def bootstrap_league_schedule(self, league_id: int):
        data = request.get_json(silent=True) or {}

        max_teams = None
        if "maxTeams" in data and data["maxTeams"] is not None:
            try:
                max_teams = int(data["maxTeams"])
            except (TypeError, ValueError):
                return jsonify({"message": "maxTeams must be an integer"}), 400

        force = bool(data.get("force", False))

        try:
            summary = self.model.bootstrap_league_schedule(
                league_id,
                max_teams=max_teams,
                force=force,
            )
            return jsonify(summary), 200
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            import traceback
            traceback.print_exc()
            return jsonify({"message": "Failed to bootstrap league schedule"}), 500

    # ------------------------------------------------------------------
    # POST /api/schedule/all
    #
    # Body:
    #   {
    #     "leagueId": 1,
    #     "weekNumber": 3,
    #     "memberId": 7
    #   }
    #
    # Returns schedule for all teams the member owns in that league/week,
    # from GameResult (no ESPN calls).
    # ------------------------------------------------------------------
    def get_member_schedule(self):
        data = request.get_json(silent=True) or {}
        league_id = data.get("leagueId")
        week_number = data.get("weekNumber")
        member_id = data.get("memberId")

        if league_id is None or week_number is None or member_id is None:
            return jsonify({
                "message": "leagueId, weekNumber, and memberId are required"
            }), 400

        try:
            league_id_int = int(league_id)
            member_id_int = int(member_id)
            week_number_int = int(week_number)

            games = self.model.get_member_games_for_week(
                league_id_int,
                member_id_int,
                week_number_int,
            )
            week = self.model.get_week_for_league(
                league_id_int,
                week_number_int,
            )
            owned_teams = self.model.get_owned_teams_for_member(
                league_id_int,
                member_id_int,
                week_number_int
            )

            # New response shape: include both week + games
            return jsonify({
                "ownedTeams": owned_teams,
                "week": week,      # can be None if not found
                "games": games,    # list[dict]
            }), 200
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            import traceback
            traceback.print_exc()
            return jsonify({"message": "Failed to get member schedule"}), 500

    # POST /api/schedule/conferenceGamesByWeek
    # {
    #   "leagueId": 1,
    #   "weekNumber": 6,
    #   "seasonYear": 2025,
    #   "sportConferenceId": 12
    # }
    def conference_games_by_week(self):
        """
        POST /api/schedule/conferenceGamesByWeek
        Body: { leagueId, weekNumber, seasonYear, sportConferenceId }
        """
        body = request.get_json(silent=True) or {}

        required = ["leagueId", "weekNumber", "seasonYear", "sportConferenceId"]
        missing = [k for k in required if body.get(k) is None]
        if missing:
            return jsonify({"message": f"Missing required fields: {missing}"}), 400

        try:
            games = self.model.get_conference_games_by_week(
                league_id=int(body["leagueId"]),
                week_number=int(body["weekNumber"]),
                season_year=int(body["seasonYear"]),
                sport_conference_id=int(body["sportConferenceId"]),
            )
            return jsonify({
                "leagueId": body["leagueId"],
                "weekNumber": body["weekNumber"],
                "seasonYear": body["seasonYear"],
                "sportConferenceId": body["sportConferenceId"],
                "games": games,
            }), 200
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            import traceback
            traceback.print_exc()
            return jsonify({"message": "Failed to get conference games by week"}), 500


    # POST /api/schedule/teamGamesBySeason
    # {
    #     "seasonYear": 2025,
    #     "sportTeamId": 183
    # }
    def team_games_by_season(self):
        """
        POST /api/schedule/teamGamesBySeason
        Body: { seasonYear, sportTeamId }
        """
        body = request.get_json(silent=True) or {}

        required = ["seasonYear", "sportTeamId"]
        missing = [k for k in required if body.get(k) is None]
        if missing:
            return jsonify({"message": f"Missing required fields: {missing}"}), 400

        try:
            games = self.model.get_team_games_by_season(
                sport_team_id=int(body["sportTeamId"]),
                season_year=int(body["seasonYear"]),
            )
            return jsonify({
                "seasonYear": body["seasonYear"],
                "sportTeamId": body["sportTeamId"],
                "games": games,
            }), 200
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            import traceback
            traceback.print_exc()
            return jsonify({"message": "Failed to get team games by season"}), 500
        
    # POST /api/schedule/createWeeks
    # {
    #     "leagueId": 2,
    # }
    def createWeeksForLeague(self):
        body = request.get_json(silent=True) or {}

        required = ["leagueId"]
        missing = [k for k in required if body.get(k) is None]
        if missing:
            return jsonify({"message": f"Missing required fields: {missing}"}), 400

        try:
            weeks = self.model.ensure_weeks_for_league(
                leagueId=int(body["leagueId"])
            )
            return jsonify({
                "leagueId": body["leagueId"],
                "weeksCreated": weeks,
            }), 201
        except ValueError as e:
            return jsonify({"message": str(e)}), 400
        except Exception:
            import traceback
            traceback.print_exc()
            return jsonify({"message": "Failed to create weeks"}), 500