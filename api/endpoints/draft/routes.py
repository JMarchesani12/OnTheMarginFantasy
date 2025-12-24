from endpoints.draft.draftEndpoints import DraftEndpoints

def setup_routes(app, engine):

    draftEndpoints = DraftEndpoints(engine)

    app.add_url_rule("/api/draft/pick", view_func=draftEndpoints.create_pick, methods=["POST"],)
