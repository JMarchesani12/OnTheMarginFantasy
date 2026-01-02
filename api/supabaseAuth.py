# supabaseAuth.py
import os
import jwt

SUPABASE_PROJECT_ID = os.environ["SUPABASE_PROJECT_ID"]
SUPABASE_JWT_SECRET = os.environ["SUPABASE_JWT_SECRET"]

ISSUER = f"https://{SUPABASE_PROJECT_ID}.supabase.co/auth/v1"

def verify_supabase_token(token: str):
    try:
        return jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            issuer=ISSUER,
        )
    except Exception as e:
        return None
