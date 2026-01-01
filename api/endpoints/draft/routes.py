from endpoints.draft.draftEndpoints import DraftEndpoints

def setup_routes(app, engine):

    draftEndpoints = DraftEndpoints(engine)

    app.add_url_rule("/api/draft/pick", view_func=draftEndpoints.create_pick, methods=["POST"])
    app.add_url_rule("/api/draft/state/<int:league_id>", view_func=draftEndpoints.state, methods=["GET"])
    app.add_url_rule("/api/draft/start", view_func=draftEndpoints.start, methods=["POST"])
    app.add_url_rule("/api/draft/pause", view_func=draftEndpoints.pause, methods=["POST"])
    app.add_url_rule("/api/draft/resume", view_func=draftEndpoints.resume, methods=["POST"])
    app.add_url_rule("/api/draft/pick-manual", view_func=draftEndpoints.create_pick_manual, methods=["POST"])
    app.add_url_rule("/api/draft/rounds/<int:sportId>", view_func=draftEndpoints.get_rounds, methods=["GET"])
    app.add_url_rule("/api/league/<int:league_id>/draft/order", view_func=draftEndpoints.set_draft_order, methods=["PUT"])