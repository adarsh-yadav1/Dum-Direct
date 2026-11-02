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

Current state: the API exposes a health route and the web app shows whether it can reach the API. Ordering features are added in later commits.

### Without Docker

Backend (Python 3.13):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest            # run the tests
uvicorn app.main:app --reload --port 8000
```

Frontend (Node 22) in a second terminal:

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

The web app should show "API is online". Interactive API documentation is at http://localhost:8000/docs.

### With Docker Compose

```bash
cp .env.example .env
docker compose up --build   # web on http://localhost:5173, API on http://localhost:8000
```

Status of this path: `docker compose config` passes, but the images have not yet been built and run end to end. This line is updated once they have.
