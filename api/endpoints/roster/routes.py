from endpoints.roster.rosterEndpoints import RosterEndpoints

def setup_routes(app, engine):

    rosterEndpoints = RosterEndpoints(engine)

    app.add_url_rule("/api/roster/memberTeams", view_func=rosterEndpoints.get_member_teams, methods=["POST"])
    app.add_url_rule("/api/roster/availableTeams", view_func=rosterEndpoints.get_available_teams, methods=["POST"])
 