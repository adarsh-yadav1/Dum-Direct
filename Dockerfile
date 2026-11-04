# One image serves the web app and the API from a single origin.

# Stage 1: build the web app.
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# Stage 2: the API, with the built web app beside it.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STATIC_DIR=/srv/static

WORKDIR /srv

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

COPY backend/app ./app
COPY backend/alembic.ini backend/start.sh ./
COPY backend/alembic ./alembic
COPY --from=web /web/dist ./static

# Run as an unprivileged user.
RUN useradd --system --create-home appuser
USER appuser

EXPOSE 8000

# Hosts that assign a port set $PORT; locally it is 8000.
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=5 \
  CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/api/health' % os.environ.get('PORT', '8000'), timeout=2).status == 200 else 1)"

CMD ["sh", "start.sh"]
