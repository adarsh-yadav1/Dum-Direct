# Engineering Design and Decision Record
Project: Direct ordering website with kitchen display (Problem 1, Hyderabadi restaurant chain)
Status: Draft v1, written before any code. Date: 2 Nov 2026. Deadline: 9 Nov 2026, 11:59 pm IST.

---

## 1. What we are building

### 1.1 Goal in one paragraph
A customer on a phone gives a delivery location, and the system automatically assigns the serving outlet from the outlets' delivery radii (the customer never chooses an outlet). The customer then orders from a short photo-led menu, pays through a mock UPI or card flow, and watches live order status. The order appears instantly on the correct outlet's kitchen screen, where staff move it through prep stages. The promised time is computed from current kitchen load, and late orders are flagged. A central admin controls one menu, with prices by city and per-outlet availability.

### 1.2 Scope decision
The brief requires a "core build" in 6 to 8 screens. Everything else is optional depth. We build in three tiers so that something complete always exists.

| Tier | Meaning | Contents |
|---|---|---|
| P0 | Must work end to end before anything else | Sign-in and roles, outlet selection and routing, menu with variants and add-ons, cart, mock payment, order creation, kitchen display with real-time updates, prep stages, prep-time estimate, menu admin (items, city prices, outlet availability, out-of-stock pause), seed data, tests, deployment |
| P1 | Well-judged depth, built only after P0 is deployed | Late-order alert and customer update, manager override of estimates, reorder suggestions, coupons, order history, manager dashboard (orders, prep time, cancellations, repeat customers) |
| P2 | Documented as cut, listed under "what we would do next" | Loyalty points and redemption, party order form, time-based menu editor UI, WhatsApp/SMS (only a logged mock), multi-city admin UI beyond a price table |

Rationale: the brief says "build a small part really well." Loyalty and party orders are in the MUST HAVE list but outside the core build, so they are the first things we cut if time is short. Time-based menus are cheap to support in the data model (a time window on a category), so the model keeps the field even if the admin UI for it is minimal.

### 1.3 Screens (8 plus sign-in)
1. Delivery location (geolocation, or search and pin a locality). The system resolves the serving outlet and shows it as information ("Delivering from Kondapur, about 35 min"), with a "Not serviceable here" state when no outlet covers the location. There is no outlet list to choose from
2. Menu (categories, photo cards, veg and non-veg marks, spice level)
3. Item sheet (portion, add-ons, quantity), a bottom sheet rather than a page
4. Cart and checkout (coupon field in P1, GST statement, ETA)
5. Mock payment (UPI or card, success and failure paths)
6. Live order tracking
7. Kitchen display (tablet, landscape, readable from two metres)
8. Menu admin (items, prices by city, outlet availability)
9. Sign-in (shared by all roles)
10. P1: manager dashboard

---

## 2. Assumptions (label each of these in the TDD)

| ID | Assumption | Why |
|---|---|---|
| A1 | Only the facts in the brief are used for the business. Outlets other than the three named in the sample data (Kondapur, Gachibowli cloud kitchen, Kukatpally) are invented seed data and marked as such | Brief rule: use only given information |
| A2 | Outlet coordinates and delivery radii are illustrative, not surveyed | No address data was provided |
| A3 | The customer's location comes from browser geolocation, or from searching a built-in list of Hyderabad localities with fixed coordinates, then adjusting a pin. No paid maps or geocoding API. Eligibility uses straight-line (haversine) distance, not road distance | Avoids API keys, so reviewers can run the app |
| A15 | Orders are delivery only. "Ready for pickup" means pickup by the delivery partner's rider, so there is no customer pickup option and no reason for the customer to choose an outlet | Rider handoff is in the brief; own pickup is not |
| A16 | When several outlets cover a location, the nearest one that can supply every cart item is assigned. Load-aware assignment (choosing the outlet with the earliest promised time) is a P1 refinement | Simple, deterministic, explainable |
| A4 | Delivery fee is zero by default and configurable per outlet. Rider handoff is a status step only | Delivery partner integration is out of scope |
| A5 | Menu prices are GST-inclusive at 5%. The GST component shown is `total * 5 / 105`, rounded to the nearest paisa | Brief: prices include 5% GST and must say so |
| A6 | Food photos are placeholders or openly licensed images, with licences listed in `ASSETS.md` | Avoids licensing risk |
| A7 | FSSAI numbers and allergen lists are fictional sample values | Real data is not provided |
| A8 | Payments are mocked. The mock behaves like a real gateway: pending, success, failure, and a webhook-style confirmation | Brief allows mocked payments |
| A9 | WhatsApp and SMS messages are written to a `notifications` table and shown in a dev log, not sent | Brief allows mocking outside systems |
| A10 | Kitchen capacity per outlet is an assumed configurable number (units per hour), not a measured value | No kitchen data given |
| A11 | Travel time to the customer is estimated at a flat minutes-per-km figure, configurable, default 3 min/km | No routing data given |
| A12 | One user belongs to one role. Kitchen staff and managers are bound to exactly one outlet. Admin is global | Keeps access control simple and testable |
| A13 | Marketing consent is a separate, unticked checkbox at sign-up and checkout. Transactional status messages do not need it | DPDP Act 2023 note in the brief |
| A14 | The peak load figure (1,200 orders per hour, about 20 per minute) is treated as an design target, verified by a small load test, not a production guarantee | Honest limits |

---

## 3. Architecture

### 3.1 Choice
- Frontend: React with TypeScript, built with Vite, styled with Tailwind CSS, served as static files. Mobile-first for customers; a separate tablet layout for the kitchen screen.
- Backend: FastAPI (Python), SQLAlchemy 2.0, Alembic migrations, Pydantic validation.
- Database: PostgreSQL.
- Real-time: Server-Sent Events (SSE) from FastAPI, fanned out through Redis pub/sub.
- Cache and rate limits: Redis (same instance).
- Auth: email and password, Argon2 or bcrypt hashes, JWT in an httpOnly cookie, role-based access control.
- Packaging: Docker Compose for local development (api, db, redis, web).

### 3.2 Why this stack
Chosen because it is the one you can debug fastest under a seven-day deadline. FastAPI gives typed validation and automatic OpenAPI docs, which reviewers can read directly. Postgres gives transactions and constraints, which matter for money and order state. Redis is already in your toolkit and is the standard solution for pub/sub across multiple API instances.

### 3.3 Real-time decision: SSE rather than WebSockets
| Criterion | SSE | WebSocket |
|---|---|---|
| Direction needed | Server to client only. Staff actions are ordinary HTTP calls | Two-way, not required |
| Reconnection | Built into the browser, with `Last-Event-ID` for resuming | Must be written by hand |
| Proxies and cheap tablets | Plain HTTP, works through most proxies | More failure modes |
| Complexity | Low | Medium |

Decision: SSE, with two safeguards. (1) Every event carries a monotonically increasing id from the `order_events` table, so a reconnecting client resumes exactly where it stopped. (2) The kitchen screen also polls a snapshot endpoint every 15 seconds as a fallback, so a dead stream cannot leave a stale screen unnoticed. A visible "connected / reconnecting" indicator is shown on the screen.

### 3.4 Component view
```
Customer phone (React) ─┐
Kitchen tablet (React) ─┼─ HTTPS ─> FastAPI ─┬─> PostgreSQL (source of truth)
Admin laptop (React)  ─┘   │  ^            └─> Redis (pub/sub, rate limit, cache)
                           │  └── SSE streams: /outlets/{id}/stream, /orders/{id}/stream
                           └── background tasks: late-order sweeper, notification writer
```
Postgres is the source of truth. Redis only carries notifications; losing Redis loses no data, because clients can always re-read the snapshot.

### 3.5 Repository layout
```
/
  README.md
  ASSETS.md
  docker-compose.yml
  .env.example
  docs/                     design, decisions, checklist, TDD source
  backend/
    app/
      main.py
      core/                 config, security, db, deps
      models/               SQLAlchemy models
      schemas/              Pydantic schemas
      api/                  routers: auth, outlets, menu, cart, orders, kitchen, admin, stream
      services/             pricing, routing, availability, prep_estimator, order_state, notifications
      seed/                 sample data loader
    tests/
    alembic/
  frontend/
    src/
      app/ (routing, layouts)
      features/ (menu, cart, checkout, tracking, kitchen, admin, auth)
      components/ (design system)
      lib/ (api client, sse, format)
  scripts/                  load test
```
Business logic lives in `services/` as pure functions where possible, so it can be tested without HTTP.

---

## 4. Data model

All money is stored as integer paise. All timestamps are stored in UTC and displayed in IST.

| Table | Key columns | Notes |
|---|---|---|
| users | id, email (stored lowercase), password_hash (Argon2id), name, phone, role (customer, kitchen, manager, admin), outlet_id, marketing_opt_in, marketing_opt_in_at, created_at | Kitchen and manager users must have an outlet; customers and admins must not (check constraint). Opt-in is recorded with the time it was given |
| outlets | id, name, kind (outlet or cloud_kitchen), city, locality, address_line, latitude, longitude, delivery_radius_km, fssai_no (14 characters), min_prep_minutes, capacity_units_per_hour, delivery_fee_paise, is_open | FSSAI number is shown on the site. Coordinates, radii and licence numbers are fictional (A1, A2, A7) |
| localities | id, name, city, latitude, longitude | Reference list behind the location search (A3). Unique per name and city |
| categories | id, name, sort_order, available_from, available_to | The optional time window gives time-based menus. A window needs both ends (check constraint) |
| menu_items | id, category_id, slug, name, description, image_url, is_veg, spice_level (0 to 3), allergens, base_prep_minutes, sort_order, is_active | Items carry no price of their own: prices live on their portions |
| item_variants | id, item_id, label, price_paise, serves, sort_order | Portions. Every item has at least one. Prices include 5% GST. Unique per item and label |
| addons | id, item_id, name, price_paise, is_active | Optional paid extras for one item. A flat list: grouped or required choices are not modelled in this build |
| city_prices | variant_id, city, price_paise | Overrides a portion's price for outlets in that city; otherwise the portion's own price applies |
| outlet_items | outlet_id, item_id, is_available, updated_by_user_id, updated_at | No row means the outlet does not offer the item. A row with is_available false means it is paused (out of stock) |
| orders | id, public_code (for example WEB-778120), user_id, outlet_id (assigned by routing, never supplied by the client), status, delivery_latitude, delivery_longitude, address_json, distance_km, routing_json (candidates, distances, reason), subtotal_paise, discount_paise, delivery_fee_paise, total_paise, gst_included_paise, placed_at, promised_at, preparing_at, ready_at, completed_at, ai_estimate_min, override_min, override_by_user_id, late_alerted_at, idempotency_key, updated_at | Delivery only (A15) |
| order_items | id, order_id, item_id, variant_id, name_snapshot, variant_label_snapshot, unit_price_paise, qty, addons_json, notes | Name and price are copied at order time, so later menu changes do not alter history |
| payments | id, order_id, method (upi or card), status, provider_ref, amount_paise, created_at, updated_at | Mock gateway (A8) |
| order_events | id, order_id, outlet_id, type, payload_json, actor_user_id, created_at | Order-scoped audit log, and the source of the real-time streams. Menu availability changes are not recorded here |
| notifications | id, user_id, order_id, channel (whatsapp or sms), template, body, created_at | Messages are recorded and never sent (A9) |
| coupons (P1), loyalty_ledger (P2) | | Not built yet |

Key constraints, enforced by the database and not only by the application: a client-supplied idempotency key is unique per customer; the order total must equal subtotal minus discount plus delivery fee, and the discount cannot exceed the subtotal; amounts are never negative; every status, role, kind and payment method is limited to its known values; foreign keys everywhere; and an index on `(outlet_id, status, placed_at)` serves the kitchen query.

---

## 5. Core flows

### 5.1 Placing an order
1. Customer sets a delivery location (coordinates plus address text). The client calls `POST /serviceability` with the coordinates. The server finds the eligible outlets (open, and distance to the location within that outlet's delivery radius), assigns one (section 5.3), and returns the assigned outlet, its menu availability, its FSSAI number and a provisional ETA. If no outlet covers the location, the response says so and the UI shows a not-serviceable state, with no menu.
2. Customer builds a cart on the client, against the assigned outlet's menu. The cart is only a proposal.
3. At checkout the client sends the cart, the delivery location and address, and an `Idempotency-Key`. It does not send an outlet id as a trusted value.
4. The server resolves the outlet again from the delivery location (the location may have changed, or an outlet may have closed since step 1), then recomputes everything from the database: availability, prices (city override, then base), add-ons, coupon, GST component, total. Client totals and the client's idea of the outlet are never trusted.
5. If an item has become unavailable at the assigned outlet, the server first tries the next eligible outlet that can supply the whole cart and, if one exists, tells the customer that the outlet changed (a visible notice, with the new ETA, before payment). If no eligible outlet can supply the whole cart, it returns a structured error listing the items and the UI offers to remove them. No silent changes.
6. The server creates the order as `pending_payment` in one transaction, together with its first `order_events` row. A repeat request with the same key returns the same order.
7. The mock payment succeeds, the order moves to `new`, an event is published, and the kitchen screen shows it within about a second.

### 5.2 Order state machine
```
pending_payment -> new -> preparing -> ready -> handed_off -> completed
        |           |         |          |
        v           v         v          v
   payment_failed  cancelled cancelled  cancelled (manager only, from ready)
```
Rules: each transition is validated in one function (`order_state.can_transition`) and is role-checked. Each transition writes an `order_events` row and publishes it. Only a kitchen or manager user of that outlet can move an order. A customer can cancel only while the status is `new`. Illegal transitions return HTTP 409.

### 5.3 Outlet routing
Routing is automatic and is a pure function of the delivery location, the cart and the current outlet state.

1. Eligible outlets: open, and `haversine(outlet, location) <= outlet.delivery_radius_km`. Each outlet has its own radius (cloud kitchens may have a different radius from dine-in outlets).
2. Rank eligible outlets by distance, with outlet id as a stable tie-break so the same input always gives the same outlet.
3. With no cart yet (browsing), assign the nearest eligible outlet and show its menu.
4. With a cart, assign the first ranked outlet where every cart item is available. If the nearest outlet cannot supply the cart but a farther one can, the customer is told that the outlet changed, with the new ETA, before paying.
5. If no outlet covers the location, return "not serviceable". If outlets cover it but none can supply the whole cart, return the list of missing items for the nearest outlet.
6. The decision is stored in the order's first `order_events` payload (candidate outlets, distances, chosen outlet, reason), so any routing result can be explained afterwards.

The customer never sees or picks from an outlet list. The assigned outlet is shown as information only. Staff and admin can see the routing reason on an order. A refinement for P1 is ranking by the earliest promised time (distance plus current kitchen load) instead of distance alone (A16).

### 5.4 Out-of-stock pause
Kitchen staff or managers toggle an item on the kitchen screen or admin screen. This writes `outlet_items.is_available = false`, publishes an event, and the menu for that outlet greys the item out within seconds. Carts holding it are caught at checkout (step 5.1.5).

### 5.5 Late orders
A background sweeper runs every 30 seconds. An order is `late` when `now > promised_at`. At `promised_at + 10 minutes`, once only, the system (1) writes a manager alert event, (2) writes a customer notification with a revised ETA, and (3) sets `late_alerted_at`. The kitchen card turns amber when within 5 minutes of the promise, then red when late.

---

## 6. The AI parts and what happens when they are wrong

### 6.1 Prep-time estimate
The estimator is a transparent, explainable model, not a black box. This is a deliberate decision: a reviewer can inspect it, it needs no external API key, and it fails predictably.

```
base       = max(item.base_prep_minutes for items in order) + 0.5 * (extra distinct units)
queue_wait = (open_units_in_new_and_preparing) / (capacity_units_per_hour / 60)
bias       = clamp(rolling average of actual / estimated for this outlet, 0.8, 1.5)   # learned from completed orders
estimate   = (base + queue_wait) * bias
promised   = now + max(estimate, outlet.min_prep_minutes) + delivery_minutes   # delivery_minutes = distance * 3 (A11)
```
"Learning" is the `bias` term: an exponentially weighted average of actual versus estimated prep time from the outlet's completed orders. With fewer than 20 samples the bias is 1.0, so cold start is safe.

When it is wrong:
- The promised time is the higher of the estimate and the outlet minimum (brief rule), so a low estimate cannot over-promise.
- A manager can set `override_min`; it replaces the estimate, is attributed, and is logged.
- The bias is clamped, so bad data cannot produce absurd promises.
- Late orders trigger the 10-minute alert (section 5.5).
- Every estimate stores its inputs in the event payload, so we can explain any promise afterwards.

### 6.2 Reorder suggestions (P1)
Rule-based: from a customer's past delivered orders, rank items by frequency weighted by recency, show up to three as "Order again". Rules: suggestions are display-only, never enter the cart without a tap, and items unavailable at the chosen outlet are hidden. A customer with no history sees nothing, with no empty box.

### 6.3 Routing and pausing
Deterministic and covered by unit tests (sections 5.3 and 5.4).

---

## 7. UI and design decisions

Principles taken from the brief: minimal, white space, restrained palette, clear type, nothing without a purpose.

- Palette: warm off-white background, near-black text, one accent colour (deep saffron or maroon). Green and red are reserved strictly for veg and non-veg marks and late-state colours, so colour always carries meaning.
- Typography: one family, with a clear scale. Prices use tabular numerals so columns align.
- Menu: single-column cards with large photos, name, short description, price, veg mark, spice dots. Sticky category chips. A short menu, not a long scroll.
- Checkout: a single page with outlet and address, items, price breakdown, payment choice, and one primary button. The target is under 60 seconds. Use saved details when signed in.
- Price statement: "All prices include 5% GST" appears on the menu footer and on checkout, with the GST amount on the bill.
- Compliance on screen: FSSAI number in the outlet header, allergen text on the item sheet.
- Kitchen display: landscape tablet, high contrast, large type readable from two metres, columns for New, Preparing, Ready. Each card shows order code, items (large), elapsed timer, promised time. Colour: neutral on time, amber approaching, red late, with an icon and text label too, so colour is not the only signal. Large touch targets (at least 56 px), one-tap stage buttons, no hover dependence, no small text. A sound chime on a new order, enabled by a "Start shift" tap because browsers block autoplay. Light client code for cheap Android tablets.
- Every screen has loading skeletons, an empty state and an error state with a retry.
- Accessibility: visible focus, labels, sufficient contrast.

---

## 8. Security and privacy
- No secrets in the repository. `.env.example` lists names only. Secrets live in the host's environment settings.
- Input validation with Pydantic on every endpoint. Length and range limits.
- Access control: dependency functions check role and outlet binding. A kitchen user cannot read or change another outlet's orders. A customer can only read their own orders. Tests prove this.
- Passwords hashed. Cookies are httpOnly, secure in production, SameSite set. CORS restricted to the frontend origin.
- Rate limiting on sign-in and order creation, backed by Redis.
- Idempotency key on order creation.
- Privacy (DPDP): collect only name, phone, email and address; a visible privacy note; marketing opt-in is separate and unticked; seed data contains only fictional people.

---

## 9. Performance and load
Peak target is 1,200 orders per hour, about 20 per minute across all outlets, which is modest for FastAPI and Postgres. The real risk is SSE connection count and the kitchen query. Mitigations: index on the kitchen query, one stream per outlet rather than per order card, Redis fan-out, and a k6 or Locust script that places orders at about 3 times peak rate and records latency from order creation to kitchen event. The result goes into the TDD as an honest measurement, including its limits (free-tier hosting).

---

## 10. Testing strategy
Priority is the logic that decides money and state.

| Area | Tests |
|---|---|
| Pricing | GST component, city price override, add-ons, coupon rules, rounding |
| Order state machine | every legal and illegal transition, role checks |
| Routing | inside and outside radius (including the exact boundary), different radius per outlet, nearest wins, stable tie-break, closed outlet skipped, reroute when the nearest outlet lacks an item, not serviceable, client-supplied outlet id ignored |
| Prep estimator | queue growth, minimum floor, override, bias clamp, cold start |
| Idempotency | duplicate submit returns one order |
| Access control | cross-outlet and cross-customer access denied |
| Real-time | one integration test: create order, receive event on outlet stream, reconnect with `Last-Event-ID` |
| Frontend | a few component tests for cart maths and the kitchen card colour rule |

---

## 11. Deployment plan
- Frontend: static host (Vercel or Netlify).
- API: Docker container on Render or Fly.io. Free tiers may sleep; the TDD says so, and the demo-login note tells reviewers to wait about 30 seconds on first load.
- Database: managed Postgres (Neon or Supabase free tier).
- Redis: Upstash or the host's Redis.
- Migrations and seed run through one command on deploy.
- Environment variable names (never values): `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `CORS_ORIGINS`, `COOKIE_SECURE`, `ENV`, `VITE_API_BASE_URL`.
- Demo accounts seeded: one customer, one kitchen user per sample outlet, one manager, one admin. Passwords are demo-only and stated in `deployment.md`.
