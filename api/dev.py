# dev.py
from dotenv import load_dotenv
load_dotenv(".env")

from api import create_app
from socketioInstance import socketio

app = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5050, debug=True)
