"""Explicit runtime composition. Definitions are safe to import without secrets."""
import os
from pathlib import Path
from dotenv import load_dotenv

API_ROOT = Path(__file__).resolve().parent


def load_runtime_environment():
    # Existing process configuration wins over local development values.
    load_dotenv(API_ROOT / '.env')


def configured_engine():
    load_runtime_environment()
    from db import get_engine
    return get_engine()


def listener_enabled():
    value = os.environ.get('DRAFT_NOTIFY_LISTENER_ENABLED', 'true').strip().lower()
    if value not in ('true', '1', 'false', '0'):
        raise ValueError('DRAFT_NOTIFY_LISTENER_ENABLED must be true, false, 1 or 0')
    return value in ('true', '1')


def start_web_listener(app, socketio, engine, *, starter=None, use_reloader=False):
    enabled = listener_enabled()
    if not enabled or (use_reloader and os.environ.get('WERKZEUG_RUN_MAIN') != 'true'):
        return
    if 'draft_notify_task' in app.extensions:
        return
    if starter is None:
        from endpoints.draft.startDraftNotifyListener import start_draft_notify_listener
        starter = start_draft_notify_listener
    app.extensions['draft_notify_task'] = starter(socketio, engine)


def create_web_app(*, engine=None, use_reloader=False):
    load_runtime_environment()
    # Check configuration before constructing resources or starting tasks.
    listener_enabled()
    from supabaseAuth import auth_configuration
    auth_configuration()
    from db import get_engine
    from api import create_app
    from socketioInstance import socketio
    engine = engine if engine is not None else get_engine()
    app = create_app(engine=engine)
    start_web_listener(app, socketio, engine, use_reloader=use_reloader)
    return app
