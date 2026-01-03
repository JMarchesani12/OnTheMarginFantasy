import os
from flask_socketio import SocketIO

cors_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173"
).split(",")

socketio = SocketIO(
    cors_allowed_origins=cors_origins,
)
