#!/bin/sh
# Container start-up: update the database schema, load demo data once, then serve the API.
# Hosts such as Render provide the port in $PORT; locally it defaults to 8000.
set -e

alembic upgrade head

# Seeds only an empty database and never touches existing data. Set SEED_ON_START=false
# to start without demo data.
if [ "${SEED_ON_START:-true}" = "true" ]; then
  python -m app.seed
fi

# Behind a host's proxy every request would appear to come from the proxy. Set
# FORWARDED_ALLOW_IPS=* on a host whose proxy is the only way in, so the real client
# address (used to throttle sign-ins) is read from X-Forwarded-For.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" \
  --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
