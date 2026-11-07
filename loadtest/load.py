"""A small load test for the order path and the live updates.

It registers customers, opens kitchen streams, then places and pays orders at a fixed rate
while the kitchen moves them along. It reports request latency and how long a live update takes
to reach a kitchen screen and a customer after payment.

    python loadtest/load.py --base http://localhost:8010 --rate 1.0 --seconds 60

Uses demo accounts and the seeded menu, so run it against a seeded local instance only.
"""

import argparse
import asyncio
import json
import statistics
import time
import uuid

import httpx

PW = "dumdirect-demo-2026"
SPOTS = [  # (latitude, longitude) of areas covered by Kondapur, Gachibowli, Kukatpally
    (17.46, 78.365), (17.4401, 78.3489), (17.4948, 78.3996),
]
KITCHENS = ["kitchen.kondapur@example.com", "kitchen.gachibowli@example.com", "kitchen.kukatpally@example.com"]


def pct(values, p):
    if not values:
        return float("nan")
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p))]


def summary(name, values_ms):
    if not values_ms:
        return f"{name:<34} no samples"
    return (f"{name:<34} n={len(values_ms):<4} p50={pct(values_ms, .5):7.0f} ms  p95={pct(values_ms, .95):7.0f} ms  "
            f"p99={pct(values_ms, .99):7.0f} ms  max={max(values_ms):7.0f} ms")


async def main(args):
    base = args.base + "/api"
    lat = {"place": [], "pay": [], "kitchen_move": [], "board": []}
    kitchen_seen, customer_seen, paid_at = {}, {}, {}
    errors = []
    limits = httpx.Limits(max_connections=400, max_keepalive_connections=200)
    timeout = httpx.Timeout(30.0, read=None)

    async def client_for(email, password=PW):
        c = httpx.AsyncClient(base_url=base, limits=limits, timeout=timeout)
        r = await c.post("/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        return c, r.json()

    # customers (Argon2 is deliberately slow, so register a few at a time)
    sem = asyncio.Semaphore(4)
    run = uuid.uuid4().hex[:6]

    async def make_customer(i):
        async with sem:
            c = httpx.AsyncClient(base_url=base, limits=limits, timeout=timeout)
            r = await c.post("/auth/register", json={"name": f"Load {i}", "email": f"load{run}-{i}@example.com", "password": PW, "marketing_opt_in": False})
            r.raise_for_status()
            return c

    customers = await asyncio.gather(*[make_customer(i) for i in range(args.customers)])
    menu = (await customers[0].get("/menu", params={"latitude": SPOTS[0][0], "longitude": SPOTS[0][1]})).json()
    dishes = {}
    for spot in SPOTS:
        m = (await customers[0].get("/menu", params={"latitude": spot[0], "longitude": spot[1]})).json()
        dishes[spot] = next(i for c in m["categories"] for i in c["items"] if i["name"] == "Veg biryani" and i["orderable"])["variants"][0]["id"]

    # kitchens: several screens per outlet, each on its own live stream
    stop = asyncio.Event()
    kitchens = []
    for email in KITCHENS:
        c, me = await client_for(email)
        kitchens.append((c, me["outlet_id"]))

    async def kitchen_listener(c, outlet_id, screen):
        async with c.stream("GET", f"/outlets/{outlet_id}/stream") as r:
            async for line in r.aiter_lines():
                if stop.is_set():
                    return
                if line.startswith("data:"):
                    ev = json.loads(line[5:])
                    if ev["type"] == "order_new":
                        kitchen_seen.setdefault((ev["order"], screen), time.perf_counter())

    listeners = [asyncio.create_task(kitchen_listener(c, o, s)) for c, o in kitchens for s in range(args.screens)]
    await asyncio.sleep(1.5)

    async def one_order(n):
        customer = customers[n % len(customers)]
        spot = SPOTS[n % len(SPOTS)]
        payload = {"latitude": spot[0], "longitude": spot[1], "address_line": f"{n} Load Test Road",
                   "lines": [{"variant_id": dishes[spot], "qty": 1 + n % 3}]}
        t = time.perf_counter()
        r = await customer.post("/orders", json=payload, headers={"Idempotency-Key": f"load-{run}-{n}"})
        lat["place"].append((time.perf_counter() - t) * 1000)
        if r.status_code != 201:
            errors.append(("place", r.status_code, r.text[:120]))
            return
        order = r.json()
        code, cursor = order["public_code"], order["last_event_id"]

        async def watch():
            async with customer.stream("GET", f"/orders/{code}/stream", params={"after": cursor}) as s:
                async for line in s.aiter_lines():
                    if line.startswith("data:") and json.loads(line[5:])["type"] == "order_new":
                        customer_seen[code] = time.perf_counter()
                        return
        watcher = asyncio.create_task(watch())
        t = time.perf_counter()
        r = await customer.post(f"/orders/{code}/pay", json={"method": "upi"})
        paid_at[code] = time.perf_counter()
        lat["pay"].append((paid_at[code] - t) * 1000)
        if r.status_code != 200:
            errors.append(("pay", r.status_code, r.text[:120]))
        kc = next(c for c, o in kitchens if o == order["outlet"]["id"])
        for status in ("preparing", "ready"):
            await asyncio.sleep(0.5)
            t = time.perf_counter()
            r = await kc.post(f"/outlets/{order['outlet']['id']}/orders/{code}/status", json={"status": status})
            lat["kitchen_move"].append((time.perf_counter() - t) * 1000)
            if r.status_code != 200:
                errors.append(("move", r.status_code, r.text[:120]))
        try:
            await asyncio.wait_for(watcher, 10)
        except asyncio.TimeoutError:
            errors.append(("customer stream never saw order_new", code))

    async def board_poller():
        c, oid = kitchens[0]
        while not stop.is_set():
            t = time.perf_counter()
            r = await c.get(f"/outlets/{oid}/orders")
            lat["board"].append((time.perf_counter() - t) * 1000)
            if r.status_code != 200:
                errors.append(("board", r.status_code))
            await asyncio.sleep(1)

    poller = asyncio.create_task(board_poller())
    started = time.perf_counter()
    tasks, n = [], 0
    while time.perf_counter() - started < args.seconds:
        tasks.append(asyncio.create_task(one_order(n)))
        n += 1
        await asyncio.sleep(1 / args.rate)
    await asyncio.gather(*tasks)
    await asyncio.sleep(2)
    stop.set()
    poller.cancel()
    for t in listeners:
        t.cancel()

    kitchen_ms = [(kitchen_seen[(c, s)] - paid_at[c]) * 1000 for (c, s) in kitchen_seen if c in paid_at]
    customer_ms = [(customer_seen[c] - paid_at[c]) * 1000 for c in customer_seen if c in paid_at]
    expected = n * args.screens
    print(f"\nOrders placed: {n} over {args.seconds}s ({args.rate}/s = {args.rate * 3600:.0f}/hour), "
          f"{len(kitchens) * args.screens} kitchen streams + up to {n} customer streams")
    for name in lat:
        print(summary(name, lat[name]))
    print(summary("update reaches a kitchen screen", kitchen_ms), f"(received {len(kitchen_ms)}/{expected})")
    print(summary("update reaches the customer", customer_ms), f"(received {len(customer_ms)}/{n})")
    print("errors:", len(errors), errors[:5])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--rate", type=float, default=1.0, help="orders per second")
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--customers", type=int, default=20)
    parser.add_argument("--screens", type=int, default=5, help="kitchen screens per outlet")
    asyncio.run(main(parser.parse_args()))
