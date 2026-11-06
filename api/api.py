import os
from flask import Flask, g, jsonify
from flask_cors import CORS
from socketioInstance import socketio
from endpoints.league.routes import setup_routes as LeagueRoutes
from endpoints.draft.routes import setup_routes as DraftRoutes
from endpoints.roster.routes import setup_routes as RosterRoutes
from endpoints.schedule.routes import setup_routes as ScheduleRoutes
from endpoints.transaction.routes import setup_routes as TransactionRoutes
from endpoints.scoring.routes import setup_routes as ScoringRoutes
from endpoints.user.routes import setup_routes as UserRoutes
from endpoints.sport.routes import setup_routes as SportRoutes
from endpoints.draft.draftSocket import register_draft_socket_handlers

from authMiddleware import install_auth_middleware

def create_app(engine=None):
    if engine is None:
        from runtime import configured_engine
        engine = configured_engine()

    app = Flask(__name__)
    from runtime import listener_enabled
    app.extensions["draft_listener_enabled"] = listener_enabled()

    @app.get("/health")
    def health():
        return {"ok": True}, 200

    @app.get("/ready")
    def ready():
        enabled = app.extensions.get('draft_listener_enabled', True)
        controller = app.extensions.get('draft_notify_listener')
        status = (controller.status() if controller is not None and enabled else
                  {'enabled': enabled, 'state': 'not_started' if enabled else 'disabled', 'category': None})
        ok = not enabled or status['state'] == 'connected'
        g.operational_readiness_response = True
        response = jsonify({'ok': ok, 'listener': status})
        response.status_code = 200 if ok else 503
        response.headers['Cache-Control'] = 'no-store'
        return response

    cors_origins = [
        o.strip()
        for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    ]

    CORS(
        app,
        resources={
            r"/api/*": {"origins": cors_origins},
            r"/socket.io/*": {"origins": cors_origins},
            r"/health": {"origins": cors_origins},
            r"/ready": {"origins": cors_origins},
        },
        supports_credentials=True,
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["X-Request-ID"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    install_auth_middleware(
        app,
        public_paths={
            "/health",
            "/ready",
            "/api/sports",
            "/api/leagues/search",
        },
        public_prefixes=[
            "/socket.io",           # allow socket.io handshake route through (see note below)
        ],
    )

    LeagueRoutes(app, engine)
    DraftRoutes(app, engine)
    RosterRoutes(app, engine)
    ScheduleRoutes(app, engine)
    TransactionRoutes(app, engine)
    ScoringRoutes(app, engine)
    UserRoutes(app, engine)
    SportRoutes(app, engine)

    socketio.init_app(app, cors_allowed_origins=cors_origins)
    register_draft_socket_handlers(engine)

    return app

if __name__ == "__main__":
    from dev import main
    main()
