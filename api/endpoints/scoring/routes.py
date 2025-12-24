from endpoints.schedule.scheduleModel import ScheduleModel
from endpoints.scoring.scoringEndpoints import ScoringEndpoints
import os
from dotenv import load_dotenv

def setup_routes(app, engine):

    load_dotenv()
    scheduleModel = ScheduleModel(engine, os.getenv("ESPN_BASE_URL"))
    scoringEndpoints = ScoringEndpoints(engine, scheduleModel)

    app.add_url_rule("/api/league/<int:league_id>/scoreWeek/<int:week_number>", view_func=scoringEndpoints.score_week, methods=["POST"])
    app.add_url_rule("/api/league/<int:league_id>/pointsAwarded", view_func=scoringEndpoints.get_points_awarded_for_weeks, methods=["POST"])
    app.add_url_rule("/api/league/<int:league_id>/scoreSeason", view_func=scoringEndpoints.compute_end_of_year_season_standings, methods=["GET"])