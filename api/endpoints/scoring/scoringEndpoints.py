# endpoints/scoring/scoringEndpoints.py

from flask import jsonify, request
import logging

from .scoringModel import ScoringModel


logger = logging.getLogger(__name__)


class ScoringEndpoints:
    """
    Flask endpoint layer for scoring-related actions:

      - POST /api/league/<league_id>/scoreWeek/<week_number>
          -> compute weekly scores for that league/week
             using global GameResult + Week + LeagueTeamSlot.

      - GET /api/league/<league_id>/standings
          -> aggregate WeeklyTeamScore + BonusPointEvent
             into season standings.
    """

    def __init__(self, db_engine, schedule_model):
        """
        db_engine: SQLAlchemy Engine instance
        schedule_model: an instance of ScheduleModel (shared with schedule endpoints)
        """
        self.scoringModel = ScoringModel(db_engine, schedule_model)

    # ------------------------------------------------------------------
    # POST /api/league/<league_id>/scoreWeek/<week_number>
    # ------------------------------------------------------------------
    def score_week(self, league_id: int, week_number: int):
        """
        Trigger scoring for a single week in a league.

        Expected route:
          POST /api/league/<int:league_id>/scoreWeek/<int:week_number>
        """
        try:
            result = self.scoringModel.compute_weekly_scores(
                league_id=league_id,
                week_number=week_number,
            )
            # result already includes leagueId, weekNumber, weekId, scores[]
            return jsonify(result), 200

        except ValueError as e:
            # Typically "Week not found", "No members", etc.
            logger.warning("ValueError in score_week: %s", e)
            return jsonify({"message": str(e)}), 400

        except Exception as e:
            logger.exception(
                "Unexpected error scoring week %s for league %s",
                week_number,
                league_id,
            )
            return jsonify({"message": "Failed to score week"}), 500
        

    # ------------------------------------------------------------------
    # POST /api/league/<league_id>/pointsAwarded
    # ------------------------------------------------------------------
    def get_points_awarded_for_weeks(self, league_id: int):
        """
        POST /api/league/<int:league_id>/pointsAwarded

        Body:
        {
        "weekNumbers": [1, 2, 3]
        }
        """
        try:
            payload = request.get_json(force=True) or {}
            week_numbers = payload.get("weekNumbers")

            if not isinstance(week_numbers, list) or not week_numbers:
                return jsonify({
                    "message": "weekNumbers must be a non-empty array of integers"
                }), 400

            # Normalize / validate
            try:
                week_numbers = [int(w) for w in week_numbers]
            except (TypeError, ValueError):
                return jsonify({
                    "message": "weekNumbers must contain only integers"
                }), 400

            result = self.scoringModel.get_weekly_points_awarded_for_league(
                league_id=league_id,
                week_numbers=week_numbers,
            )

            return jsonify({
                "weekNumbers": week_numbers,
                "results": result,
            }), 200

        except Exception:
            logger.exception(
                "Unexpected error getting pointsAwarded for league %s",
                league_id,
            )
            return jsonify({"message": "Failed to get points awarded"}), 500

    # ------------------------------------------------------------------
    # GET /api/league/<league_id>/standings
    # ------------------------------------------------------------------
    def compute_end_of_year_season_standings(self, league_id: int):
        """
        Return season standings for a league:

        - weeklyPoints = sum of WeeklyTeamScore.pointsAwarded
        - bonusPoints  = sum of BonusPointEvent.points
        - totalPoints  = weeklyPoints + bonusPoints

        Expected route:
          GET /api/league/<int:league_id>/standings
        """
        try:
            result = self.scoringModel.compute_end_of_year_season_standings(league_id)
            return jsonify(result), 200

        except ValueError as e:
            logger.warning("ValueError in compute_end_of_year_season_standings: %s", e)
            return jsonify({"message": str(e)}), 400

        except Exception as e:
            logger.exception(
                "Unexpected error getting standings for league %s",
                league_id,
            )
            return jsonify({"message": "Failed to get standings"}), 500
