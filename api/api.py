from flask import Flask
from flask_cors import CORS
from db import engine
from endpoints.league.routes import setup_routes as LeagueRoutes
from endpoints.draft.routes import setup_routes as DraftRoutes
from endpoints.roster.routes import setup_routes as RosterRoutes
from endpoints.schedule.routes import setup_routes as ScheduleRoutes
from endpoints.transaction.routes import setup_routes as TransactionRoutes
from endpoints.scoring.routes import setup_routes as ScoringRoutes
from endpoints.user.routes import setup_routes as UserRoutes
from endpoints.sport.routes import setup_routes as SportRoutes

def create_app():

    app = Flask(__name__)
    CORS(app)

    LeagueRoutes(app, engine)
    DraftRoutes(app, engine)
    RosterRoutes(app, engine)
    ScheduleRoutes(app, engine)
    TransactionRoutes(app, engine)
    ScoringRoutes(app, engine)
    UserRoutes(app, engine)
    SportRoutes(app, engine)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5050, debug=True)