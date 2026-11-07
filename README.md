# DumDirect

DumDirect is a direct ordering platform for a Hyderabadi biryani restaurant chain. Customers give a delivery location, and the system assigns the serving outlet automatically from each outlet's delivery radius. Orders reach that outlet's kitchen screen in real time, where staff move them through preparation stages. The promised delivery time comes from an explainable prep-time estimate based on current kitchen load.

This is a take-home project built for a client brief. The client is referred to as "Company A" in the brief, so DumDirect is a working name and not the client's brand. All outlet details, FSSAI numbers, menu items and customers are fictional sample data. Payments, WhatsApp and SMS are mocked.

## Status

Built and working end to end: customer ordering, automatic outlet assignment, the kitchen display with live updates, the prep-time estimate and the menu admin. Payment is a mock. Dish photos are linked from licensed sources and are optional (see `backend/app/seed/images.py`); dishes without one show a plain tile.

## What it does

| Area | Address | What it does |
|---|---|---|
| Customer app | `/` | Pick a delivery area (search or the phone's position), see which kitchen will cook and how soon, browse the menu (portions, add-ons, time-limited sections, sold-out marks), cart, checkout, test-mode payment, live order tracking |
| Kitchen display | `/kitchen` | Per-outlet board of New, Cooking, Ready and Out for delivery. Orders arrive live with an optional chime. One action per order, late orders flagged, dish switches, and (managers only) a promised-time change |
| Menu admin | `/admin` | One menu for every outlet: prices and per-city prices, hide or show dishes, choose which outlets offer each dish, add dishes |
| Prep-time estimate | in the order flow | `(longest dish time + queue wait) x outlet history factor`, with the outlet's own minimum, travel time, a manager override and a late alert 10 minutes past the promise |

The outlet is never chosen by the customer. It is picked from the delivery location and each outlet's own delivery radius, falling back to a farther outlet when the nearest cannot cook everything in the cart.

## Technology

- Frontend: React, TypeScript, Vite, Tailwind CSS (fonts bundled, no external requests)
- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic
- Data: PostgreSQL; Redis for the shared sign-in throttle
- Real-time updates: Server-Sent Events from the order event log, with a 15-second polling fallback
- Local environment: Docker Compose; deployment: one container, Postgres and Redis (`render.yaml`)

## Tests

```bash
cd backend && .venv/bin/python -m pytest      # 360 tests: API, access control, routing, estimator, streams
cd frontend && npm test                        # cart, formatting and order helpers
```

## Documentation

- [Engineering design](docs/01-engineering-design.md)

## Running locally

### Without Docker

Backend (Python 3.13):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest            # run the tests (they use an in-memory SQLite database)

# From here on a PostgreSQL 16 database is needed. Set DATABASE_URL (see .env.example), then:
alembic upgrade head        # create the tables
python -m app.seed          # load outlets, menu, demo accounts and the three sample orders
uvicorn app.site:site --reload --port 8000   # the API, under /api
```

Frontend (Node 22) in a second terminal:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

The web app should show "API is online". Interactive API documentation is at http://localhost:8000/api/docs.

### Demo data

`python -m app.seed` fills an empty database and does nothing if data already exists. `python -m app.seed --reset` rebuilds everything and shifts the three sample orders so they look current; one of them is 4 minutes past its promise. All people, outlets, FSSAI numbers and addresses are invented.

Every demo account uses the password in `DEMO_PASSWORD` (the default is in `.env.example`). It is a published demo credential, not a secret. Sign in with `POST /auth/login` (try it at http://localhost:8000/api/docs).

| Account | Role | Outlet |
|---|---|---|
| ananya@example.com | customer (gave marketing consent) | none |
| rahul@example.com | customer | none |
| kitchen.kondapur@example.com | kitchen | Kondapur |
| kitchen.gachibowli@example.com | kitchen | Gachibowli cloud kitchen |
| kitchen.kukatpally@example.com | kitchen | Kukatpally |
| manager.kukatpally@example.com | manager | Kukatpally |
| admin@example.com | admin | all |

### Sign-in and access control

- All API routes live under `/api`. `POST /api/auth/register` creates customer accounts only; unknown fields such as `role` are rejected. Marketing opt-in is off unless the customer ticks it, and the time it was given is recorded.
- `POST /api/auth/login`, `POST /api/auth/logout` and `GET /api/auth/me`. The session is a 12-hour token in an httpOnly cookie; the user's role and outlet are read from the database on every request.
- Kitchen and manager accounts can reach only their own outlet; admins reach all; customers reach only their own orders. Only an outlet's manager or an admin may override a promised time.
- Protections: Argon2id password hashes, one identical answer for a wrong password and an unknown email, a refusal of cross-site writes from origins not in `CORS_ORIGINS`, and a throttle of five failed sign-ins per address and email in 15 minutes.
- With `REDIS_URL` set, the throttle counts are shared between server instances and survive restarts. Without it, or while Redis is down, they fall back to the server's memory, which protects one instance but resets on restart.

### With Docker Compose

```bash
cp .env.example .env
docker compose up --build   # one container serves the web app and the API on http://localhost:8000
```

The web app and the API are served from one address on purpose. The sign-in cookie then stays first-party, which browsers that block third-party cookies (Safari, iPhone) require; it also removes the need for CORS in production. The same shape is used for deployment: one container, plus PostgreSQL and Redis.

Status of this path: built and run on Ubuntu with Docker Engine and Compose. The container log shows the migration, the seed and the server start, and the health check passes.

## Deploying

`render.yaml` describes the whole deployment (one web service built from the `Dockerfile`, a Postgres database and a Redis instance). See `deployment.md` in the submission for the steps and the environment variable names. In production the app refuses to start without a strong `JWT_SECRET` and `COOKIE_SECURE=true`.
