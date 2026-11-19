from endpoints.sport.sportEndpoints import SportEndpoints

def setup_routes(app, engine):

    sportEndpoints = SportEndpoints(engine)

    app.add_url_rule("/api/sports", view_func=sportEndpoints.get_sports, methods=["GET"])

    app.add_url_rule("/api/team-search/catalog", view_func=sportEndpoints.get_team_search_catalog, methods=["GET"])
