# DumDirect

DumDirect is a direct ordering platform for a Hyderabadi biryani restaurant chain. Customers give a delivery location, and the system assigns the serving outlet automatically from each outlet's delivery radius. Orders reach that outlet's kitchen screen in real time, where staff move them through preparation stages. The promised delivery time comes from an explainable prep-time estimate based on current kitchen load.

This is a take-home project built for a client brief. The client is referred to as "Company A" in the brief, so DumDirect is a working name and not the client's brand. All outlet details, FSSAI numbers, menu items and customers are fictional sample data. Payments, WhatsApp and SMS are mocked.

## Status

Work in progress. The repository is being built in the open, one reviewable commit at a time. This README is updated as each part starts to work, so it only describes what exists.

## Planned scope

| Area | Description |
|---|---|
| Customer app | Delivery location, automatic outlet assignment, menu with photos, portions and add-ons, cart, mock UPI and card payment, live order tracking |
| Kitchen display | Per-outlet live order board with timers, preparation stages, ready for pickup and rider handoff, readable from two metres |
| Menu admin | Items, prices by city, outlet availability, out-of-stock pause |
| Prep-time estimate | Transparent formula based on kitchen load, with an outlet minimum, a manager override and a late-order alert |

## Technology

- Frontend: React, TypeScript, Vite, Tailwind CSS
- Backend: FastAPI, SQLAlchemy, Alembic, Pydantic
- Data: PostgreSQL, with Redis for real-time fan-out
- Real-time updates: Server-Sent Events
- Local environment: Docker Compose

## Documentation

- [Engineering design](docs/01-engineering-design.md)

## Running locally

Current state: the database schema, sample data and demo accounts exist, the API exposes a health route, and the web app shows whether it can reach the API. Ordering is added in later commits.

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
uvicorn app.main:app --reload --port 8000
```

Frontend (Node 22) in a second terminal:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

The web app should show "API is online". Interactive API documentation is at http://localhost:8000/docs.

### Demo data

`python -m app.seed` fills an empty database and does nothing if data already exists. `python -m app.seed --reset` rebuilds everything and shifts the three sample orders so they look current; one of them is 4 minutes past its promise. All people, outlets, FSSAI numbers and addresses are invented.

Every demo account uses the password in `DEMO_PASSWORD` (the default is in `.env.example`). It is a published demo credential, not a secret. Sign in with `POST /auth/login` (try it at http://localhost:8000/docs).

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

- `POST /auth/register` creates customer accounts only; unknown fields such as `role` are rejected. Marketing opt-in is off unless the customer ticks it, and the time it was given is recorded.
- `POST /auth/login`, `POST /auth/logout` and `GET /auth/me`. The session is a 12-hour token in an httpOnly cookie; the user's role and outlet are read from the database on every request.
- Kitchen and manager accounts can reach only their own outlet; admins reach all; customers reach only their own orders. Only an outlet's manager or an admin may override a promised time.
- Protections: Argon2id password hashes, one identical answer for a wrong password and an unknown email, a refusal of cross-site writes from origins not in `CORS_ORIGINS`, and a throttle of five failed sign-ins per address and email in 15 minutes.
- Known limit: the throttle counts live in the server's memory, so they reset on restart and are not shared between instances.

### With Docker Compose

```bash
cp .env.example .env
docker compose up --build   # web on http://localhost:5173, API on http://localhost:8000
```

Status of this path: `docker compose config` passes, but the images have not yet been built and run end to end. This line is updated once they have.
