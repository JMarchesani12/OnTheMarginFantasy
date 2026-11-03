"""Database construction is explicit; importing this module reads no configuration."""
import os
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def get_engine() -> Engine:
    url = os.environ.get('SUPABASE_DB_URL')
    if not url:
        raise RuntimeError('SUPABASE_DB_URL is not set')
    return create_engine(url, pool_pre_ping=True)
