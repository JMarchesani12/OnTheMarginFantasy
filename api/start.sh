#!/usr/bin/env bash
set -e

# Resolve the app and optional local configuration relative to this script.
cd "$(dirname "$0")"
# Gunicorn needs PORT before loading wsgi; Python loads the optional .env too.
PORT="${PORT:-$(python3 -c 'from runtime import load_runtime_environment; import os; load_runtime_environment(); print(os.environ.get("PORT", "5050"))')}"
exec gunicorn -k eventlet -w 1 -b "0.0.0.0:${PORT}" wsgi:app
