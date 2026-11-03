# auth_middleware.py
from flask import request, g
from supabaseAuth import verify_supabase_token
from httpBoundary import authentication_error, install_http_boundary

def install_auth_middleware(app, public_paths=None, public_prefixes=None):
    """
    App-level auth interceptor:
    - Verifies Supabase JWT on every request
    - Skips allowlisted routes
    """
    install_http_boundary(app)
    public_paths = set(public_paths or [])
    public_prefixes = list(public_prefixes or [])

    @app.before_request
    def _auth_interceptor():
        path = request.path

        # Let CORS preflight through
        if request.method == "OPTIONS":
            return None

        # Allow exact public paths
        if path in public_paths:
            return None

        # Allow public prefixes
        for p in public_prefixes:
            if path.startswith(p):
                return None

        # Require Bearer token for everything else
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return authentication_error('auth_token_missing')

        token = auth.split(" ", 1)[1].strip()
        if not token:
            return authentication_error('auth_token_missing')

        claims = verify_supabase_token(token)
        if not claims:
            return authentication_error('auth_token_invalid')

        # Available in endpoints via g.user
        g.user = claims
        return None
