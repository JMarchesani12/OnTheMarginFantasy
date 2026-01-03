#!/usr/bin/env bash
set -e

# load local env vars for local prod-style runs
set -a
source .env
set +a

exec gunicorn -k eventlet -w 1 -b 0.0.0.0:${PORT:-5050} wsgi:app
