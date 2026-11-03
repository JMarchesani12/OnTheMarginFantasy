"""Explicit production entry point, loaded by gunicorn's eventlet worker."""
import eventlet
eventlet.monkey_patch()

from runtime import create_web_app

app = create_web_app()
