from endpoints.schedule.scheduleEndpoints import ScheduleEndpoints
import os
from dotenv import load_dotenv

def setup_routes(app, engine):

    load_dotenv()
    scheduleEndpoints = ScheduleEndpoints(engine, os.getenv("ESPN_BASE_URL"))

    app.add_url_rule("/api/schedule/all", view_func=scheduleEndpoints.get_member_schedule, methods=["POST"])
    app.add_url_rule("/api/schedule/conferenceGamesByWeek", view_func=scheduleEndpoints.conference_games_by_week, methods=["POST"])
    app.add_url_rule("/api/schedule/teamGamesBySeason", view_func=scheduleEndpoints.team_games_by_season, methods=["POST"])
    app.add_url_rule("/api/schedule/createWeeks", view_func=scheduleEndpoints.createWeeksForLeague, methods=["POST"])