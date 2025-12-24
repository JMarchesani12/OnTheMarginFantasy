# routes.py
from endpoints.user.userEndpoints import UserEndpoints


def setup_routes(app, engine):
    userEndpoints = UserEndpoints(engine)

    app.add_url_rule("/api/user", view_func=userEndpoints.create_user, methods=["POST"])
