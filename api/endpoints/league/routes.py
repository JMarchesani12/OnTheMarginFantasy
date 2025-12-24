from endpoints.league.leagueEndpoints import LeagueEndpoints

def setup_routes(app, engine):

    leagueEndpoints = LeagueEndpoints(engine)

    app.add_url_rule("/api/league/create", view_func=leagueEndpoints.create_league, methods=["POST"])
    app.add_url_rule("/api/league/byUser", view_func=leagueEndpoints.get_leagues_by_user, methods=["POST"])
    app.add_url_rule("/api/league/<int:league_id>/members", view_func=leagueEndpoints.get_league_members, methods=["GET"])
    app.add_url_rule("/api/league/<int:league_id>/conferences", view_func=leagueEndpoints.get_league_conferences, methods=["GET"])