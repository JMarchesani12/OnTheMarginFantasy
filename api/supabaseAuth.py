"""HS256 token verification with configuration resolved at execution time."""
import os
import jwt


def auth_configuration():
    values = []
    for name in ('SUPABASE_PROJECT_ID', 'SUPABASE_JWT_SECRET'):
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f'{name} is not set')
        values.append(value)
    project_id, secret = values
    return f'https://{project_id}.supabase.co/auth/v1', secret


def __getattr__(name):
    # Preserve explicit legacy/test imports without reading secrets on module import.
    if name in ('ISSUER', 'SUPABASE_PROJECT_ID', 'SUPABASE_JWT_SECRET'):
        issuer, secret = auth_configuration()
        return {'ISSUER': issuer, 'SUPABASE_PROJECT_ID': os.environ['SUPABASE_PROJECT_ID'],
                'SUPABASE_JWT_SECRET': secret}[name]
    raise AttributeError(name)


def verify_supabase_token(token: str):
    issuer, secret = auth_configuration()
    try:
        return jwt.decode(token, secret, algorithms=['HS256'],
                          audience='authenticated', issuer=issuer)
    except Exception:
        return None
