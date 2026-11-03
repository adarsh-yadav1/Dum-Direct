#!/bin/sh
# Container start-up: bring the database schema up to date, then serve the API.
# Hosts such as Render provide the port in $PORT; locally it defaults to 8000.
set -e

alembic upgrade head

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
