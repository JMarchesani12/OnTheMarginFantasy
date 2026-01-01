import socketio
import time

LEAGUE_ID = 16

sio = socketio.Client()

@sio.event
def connect():
    print("connected")
    sio.emit("draft:join", {"leagueId": LEAGUE_ID})

@sio.on("draft:snapshot")
def on_snapshot(data):
    print("snapshot received keys:", list(data.keys()))
    snap = data.get("snapshot") or {}
    state = snap.get("state")
    print("draft state:", state)

@sio.on("draft:updated")
def on_updated(data):
    print("updated:", data.get("type"))
    snap = data.get("snapshot") or {}
    print("state now:", (snap.get("state") or {}).get("currentOverallPickNumber"))

@sio.event
def disconnect():
    print("disconnected")

sio.connect("http://127.0.0.1:5050", transports=["websocket"])
time.sleep(60)
sio.disconnect()
