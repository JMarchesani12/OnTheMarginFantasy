# routes.py
from endpoints.user.userEndpoints import UserEndpoints


def setup_routes(app, engine):
    userEndpoints = UserEndpoints(engine)

    app.add_url_rule("/api/user/<int:user_id>", view_func=userEndpoints.get_user, methods=["GET"])
    app.add_url_rule("/api/user/byUuid/<uuid>", view_func=userEndpoints.get_user_by_uuid, methods=["GET"])
    app.add_url_rule("/api/user", view_func=userEndpoints.create_user, methods=["POST"])
    app.add_url_rule("/api/user/<int:user_id>", view_func=userEndpoints.update_user, methods=["PATCH"])