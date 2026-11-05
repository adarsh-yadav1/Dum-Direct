import asyncio
import contextlib
import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import stream as stream_module
from app.core.sweeper import sweep_once
from app.models import Order, OrderEvent
from app.services.events import events_after, format_sse, latest_event_id
from tests.test_kitchen_api import as_user, move, paid_order, promise, staff  # noqa: F401
from tests.test_orders_api import body, login, noon, place, seeded, variant  # noqa: F401


def parse(text):
    """Events (id, decoded data) and comment lines from raw SSE text."""
    events, comments = [], []
    for block in text.strip().split("\n\n"):
        lines = block.split("\n")
        if lines[0].startswith(":"):
            comments.append(lines[0])
        elif lines[0].startswith("id:"):
            events.append((int(lines[0][3:]), json.loads(lines[1][len("data: "):])))
    return events, comments


@pytest.fixture()
def fast(monkeypatch):
    monkeypatch.setattr(stream_module, "stream_timing", lambda: (0.01, 0.05, 0.3))


# --- the stream loop, with a scripted source --------------------------------------------------


class FakeRequest:
    def __init__(self, disconnect_after=10**9):
        self.calls, self.limit = 0, disconnect_after

    async def is_disconnected(self):
        self.calls += 1
        return self.calls > self.limit


def run_stream(fetch, after=0, request=None):
    async def collect():
        out = []
        async for chunk in stream_module.event_stream(
            request or FakeRequest(), lambda: contextlib.nullcontext(None), fetch, after
        ):
            out.append(chunk)
        return "".join(out)

    return asyncio.run(collect())


def test_stream_replays_then_continues_from_the_last_id_it_sent(fast):
    seen = []
    script = [[{"id": 5, "type": "a"}, {"id": 6, "type": "b"}], [{"id": 9, "type": "c"}]]

    def fetch(_db, after):
        seen.append(after)
        return script.pop(0) if script else []

    events, _ = parse(run_stream(fetch, after=4))
    assert [e[0] for e in events] == [5, 6, 9]
    assert seen[:3] == [4, 6, 9]  # each poll asks only for what is new


def test_stream_sends_keep_alives_when_quiet(fast):
    _, comments = parse(run_stream(lambda _db, _after: []))
    assert comments and set(comments) == {": keep-alive"}


def test_stream_stops_when_the_client_goes_away(fast):
    request = FakeRequest(disconnect_after=2)
    run_stream(lambda _d, _a: [], request=request)
    assert request.calls == 3  # asked, asked, then saw the disconnect and stopped


def test_stream_ends_by_itself_so_the_browser_reconnects(fast):
    started = asyncio.new_event_loop().time()
    run_stream(lambda _d, _a: [])
    assert asyncio.new_event_loop().time() - started < 2


def test_a_full_page_is_followed_without_waiting(monkeypatch):
    monkeypatch.setattr(stream_module, "stream_timing", lambda: (5.0, 60.0, 0.5))  # a 5 s sleep would blow the cap
    pages = [[{"id": i, "type": "x"} for i in range(1, 101)], [{"id": 101, "type": "x"}]]
    events, _ = parse(run_stream(lambda _d, _a: pages.pop(0) if pages else [], after=0))
    assert len(events) == 101


def test_format_sse_carries_the_id_for_resume():
    text = format_sse({"id": 7, "type": "order_new"})
    assert text.startswith("id: 7\ndata: ") and text.endswith("\n\n")


# --- the event log ----------------------------------------------------------------------------


def test_events_are_scoped_to_the_outlet_and_resume_after_a_cursor(client, engine, staff, noon):
    mine = paid_order(client, engine, "key-0000-0001")
    paid_order(client, engine, "key-0000-0002", place_name="Kukatpally")
    with Session(engine) as db:
        events = events_after(db, 0, outlet_id=1)
        assert {e["order"] for e in events} == {mine}
        first = events[0]["id"]
        assert [e["id"] for e in events_after(db, first, outlet_id=1)] == [e["id"] for e in events[1:]]
        assert latest_event_id(db, outlet_id=1) == events[-1]["id"]
        assert events_after(db, events[-1]["id"], outlet_id=1) == []


def test_customers_see_milestones_without_staff_internals(client, engine, staff, noon):
    code = paid_order(client, engine)
    as_user(client, "chef@example.com")
    move(client, 1, code, "preparing")
    with Session(engine) as db:
        db.add(OrderEvent(order_id=db.scalars(select(Order)).one().id, outlet_id=1, type="order_late", payload_json={"minutes_late": 12}))
        db.commit()
        order_id = db.scalars(select(Order)).one().id
        staff_view = events_after(db, 0, order_id=order_id)
        customer_view = events_after(db, 0, order_id=order_id, customer=True)
    assert "order_late" in {e["type"] for e in staff_view}
    assert "order_late" not in {e["type"] for e in customer_view}
    assert [e["type"] for e in customer_view] == ["order_created", "payment_succeeded", "order_new", "order_preparing"]
    assert set(next(e for e in customer_view if e["type"] == "order_new")["data"]) == {"promised_at"}
    assert not any("actor" in json.dumps(e) for e in customer_view)


# --- endpoints --------------------------------------------------------------------------------


def read_stream(client, url, **kwargs):
    with client.stream("GET", url, **kwargs) as response:
        return response.status_code, response.headers, "".join(response.iter_text())


def test_kitchen_stream_replays_events_after_the_cursor(client, engine, staff, noon, fast):
    code = paid_order(client, engine)
    as_user(client, "chef@example.com")
    board = client.get("/outlets/1/orders").json()
    move(client, 1, code, "preparing")
    status, headers, text = read_stream(client, f"/outlets/1/stream?after={board['cursor']}")
    events, _ = parse(text)
    assert status == 200 and headers["content-type"].startswith("text/event-stream")
    assert headers["cache-control"] == "no-cache" and headers["x-accel-buffering"] == "no"
    assert [e[1]["type"] for e in events] == ["order_preparing"]
    assert events[0][1]["order"] == code


def test_last_event_id_header_beats_the_query(client, engine, staff, noon, fast):
    code = paid_order(client, engine)
    as_user(client, "chef@example.com")
    move(client, 1, code, "preparing")
    newest = client.get("/outlets/1/orders").json()["cursor"]
    _, _, text = read_stream(client, "/outlets/1/stream?after=0", headers={"Last-Event-ID": str(newest)})
    assert parse(text)[0] == []


def test_a_stream_with_no_cursor_is_live_only(client, engine, staff, noon, fast):
    paid_order(client, engine)
    as_user(client, "chef@example.com")
    assert parse(read_stream(client, "/outlets/1/stream")[2])[0] == []


@pytest.mark.parametrize("url", ["/outlets/1/stream?after=-1", "/outlets/1/stream?after=x", "/outlets/1/events?after=x"])
def test_bad_cursors_are_rejected(client, engine, staff, noon, url):
    as_user(client, "chef@example.com")
    assert client.get(url).status_code == 422
    assert client.get("/outlets/1/stream", headers={"Last-Event-ID": "abc"}).status_code == 422


def test_streams_are_limited_to_the_right_people(client, engine, staff, noon, fast):
    assert client.get("/outlets/1/stream").status_code == 401
    as_user(client, "cust@example.com")
    assert client.get("/outlets/1/stream").status_code == 403
    as_user(client, "chef3@example.com")
    assert client.get("/outlets/1/stream").status_code == 403
    assert client.get("/outlets/1/events").status_code == 403


def test_customer_stream_shows_only_their_own_order(client, engine, staff, noon, fast):
    code = paid_order(client, engine)
    as_user(client, "cust@example.com")
    order = client.get(f"/orders/{code}").json()
    assert order["last_event_id"] > 0
    _, _, text = read_stream(client, f"/orders/{code}/stream?after=0")
    assert [e[1]["type"] for e in parse(text)[0]] == ["order_created", "payment_succeeded", "order_new"]
    assert parse(read_stream(client, f"/orders/{code}/stream?after={order['last_event_id']}")[2])[0] == []

    with Session(engine) as db:
        from app.core.security import hash_password
        from app.models import User
        db.add(User(email="other@example.com", name="O", role="customer", password_hash=hash_password("password123")))
        db.commit()
    as_user(client, "other@example.com")
    assert client.get(f"/orders/{code}/stream").status_code == 404
    assert client.get(f"/orders/{code}/events").status_code == 404
    as_user(client, "chef@example.com")
    assert client.get(f"/orders/{code}/stream").status_code == 403


def test_polling_fallback_returns_the_same_events_and_a_cursor(client, engine, staff, noon):
    code = paid_order(client, engine)
    as_user(client, "chef@example.com")
    move(client, 1, code, "preparing")
    data = client.get("/outlets/1/events?after=0").json()
    assert [e["type"] for e in data["events"]][-1] == "order_preparing"
    assert data["cursor"] == data["events"][-1]["id"]
    assert client.get(f"/outlets/1/events?after={data['cursor']}").json() == {"events": [], "cursor": data["cursor"]}
    as_user(client, "cust@example.com")
    mine = client.get(f"/orders/{code}/events?after=0").json()
    assert [e["type"] for e in mine["events"]] == ["order_created", "payment_succeeded", "order_new", "order_preparing"]


def test_manager_override_reaches_the_customer_with_the_new_time(client, engine, staff, noon):
    code = paid_order(client, engine)
    as_user(client, "manager@example.com")
    promise(client, 1, code, 25)
    as_user(client, "cust@example.com")
    events = client.get(f"/orders/{code}/events?after=0").json()["events"]
    changed = next(e for e in events if e["type"] == "promise_overridden")
    assert set(changed["data"]) == {"promised_at"}


# --- background sweeper -----------------------------------------------------------------------


def test_the_background_sweep_flags_late_orders_without_anyone_watching(client, engine, staff, noon):
    from datetime import timedelta

    from app.core.clock import utcnow

    paid_order(client, engine)
    with Session(engine) as db:
        db.scalars(select(Order)).one().promised_at = utcnow() - timedelta(minutes=30)
        db.commit()
    opener = lambda: Session(engine, expire_on_commit=False)  # noqa: E731
    assert sweep_once(opener) == 1
    assert sweep_once(opener) == 0
