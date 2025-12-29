from endpoints.league.leagueEndpoints import LeagueEndpoints

def setup_routes(app, engine):

    leagueEndpoints = LeagueEndpoints(engine)

    app.add_url_rule("/api/league/<int:league_id>", view_func=leagueEndpoints.get_league, methods=["GET"])

    app.add_url_rule("/api/league/create", view_func=leagueEndpoints.create_league, methods=["POST"])
    app.add_url_rule("/api/league/byUser", view_func=leagueEndpoints.get_leagues_by_user, methods=["POST"])
    app.add_url_rule("/api/league/<int:league_id>/members", view_func=leagueEndpoints.get_league_members, methods=["GET"])
    app.add_url_rule("/api/league/<int:league_id>/conferences", view_func=leagueEndpoints.get_league_conferences, methods=["GET"])
    app.add_url_rule("/api/league/<int:league_id>", view_func=leagueEndpoints.update_league, methods=["PATCH"])
    
    app.add_url_rule("/api/league/<int:league_id>/joinRequest", view_func=leagueEndpoints.join_request, methods=["POST"])
    app.add_url_rule("/api/league/<int:league_id>/joinRequests", view_func=leagueEndpoints.join_requests, methods=["POST"])
    app.add_url_rule("/api/league/<int:league_id>/joinRequests/<int:request_id>/approve", view_func=leagueEndpoints.add_user_to_league, methods=["POST"])
    app.add_url_rule("/api/league/<int:league_id>/joinRequests/<int:request_id>/deny", view_func=leagueEndpoints.deny_join, methods=["POST"])
    app.add_url_rule("/api/league/<int:league_id>/joinRequests/<int:request_id>/cancel", view_func=leagueEndpoints.cancel_join, methods=["POST"])
    app.add_url_rule("/api/league/<int:league_id>/members/<int:member_id>", view_func=leagueEndpoints.remove_member, methods=["DELETE"])

    app.add_url_rule("/api/leagues/search", view_func=leagueEndpoints.search_leagues, methods=["GET"])

    app.add_url_rule("/api/league/<int:league_id>", view_func=leagueEndpoints.delete_league, methods=["DELETE"])

    app.add_url_rule("/api/league/leagueMember/<int:member_id>", view_func=leagueEndpoints.patch_league_member, methods=["PATCH"])