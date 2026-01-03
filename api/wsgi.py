# wsgi.py
import os
from api import create_app
from socketioInstance import socketio

app = create_app()

# Optional: if you want a single place to start dev too:
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050, debug=True)
