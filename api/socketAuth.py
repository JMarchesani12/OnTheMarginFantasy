# socket_auth.py
from flask import request
from supabaseAuth import verify_supabase_token

def get_socket_user():
    auth = request.args.get("token")  # fallback (not preferred)
    if not auth:
        auth = request.environ.get("socketio.auth", {}).get("token")

    if not auth:
        return None

    return verify_supabase_token(auth)
