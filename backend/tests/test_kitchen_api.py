from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.security import hash_password
from app.models import Order, OrderEvent, User
from app.services.kitchen import LATE_ALERT_MINUTES, sweep_late_orders
from tests.test_orders_api import body, login, noon, place, seeded, variant  # noqa: F401


@pytest.fixture()
def staff(engine, seeded):  # noqa: F811
    with Session(engine) as db:
        for email, role, outlet in [
            ("manager@example.com", "manager", 1),
            ("chef3@example.com", "kitchen", 3),
            ("manager3@example.com", "manager", 3),
            ("admin@example.com", "admin", None),
        ]:
            db.add(User(email=email, name=email, role=role, outlet_id=outlet, password_hash=hash_password("password123")))
        db.commit()


def as_user(client, email):
    client.post("/auth/logout")
    login(client, email)


def paid_order(client, engine, key="key-0000-0001", place_name="Kondapur", item="Veg biryani", label="Regular"):
    as_user(client, "cust@example.com")
    v = variant(engine, item, label)
    code = place(client, body(engine, [{"variant_id": v.id, "qty": 1}], place=place_name), key).json()["public_code"]
    assert client.post(f"/orders/{code}/pay", json={"method": "upi"}).status_code == 200
    return code


def move(client, outlet, code, status):
    return client.post(f"/outlets/{outlet}/orders/{code}/status", json={"status": status})


def events(engine):
    with Session(engine) as db:
        return [e.type for e in db.scalars(select(OrderEvent).order_by(OrderEvent.id))]


# --- who can see the board --------------------------------------------------------------------


def test_board_needs_sign_in_and_the_right_outlet(client, engine, staff, noon):
    assert client.get("/outlets/1/orders").status_code == 401
    as_user(client, "cust@example.com")
    assert client.get("/outlets/1/orders").status_code == 403
    as_user(client, "chef3@example.com")
    assert client.get("/outlets/1/orders").status_code == 403
    assert client.get("/outlets/3/orders").status_code == 200
    as_user(client, "chef@example.com")
    assert client.get("/outlets/1/orders").status_code == 200
    as_user(client, "admin@example.com")
    assert client.get("/outlets/1/orders").status_code == 200


def test_board_shows_paid_open_orders_oldest_first(client, engine, staff, noon):
    first = paid_order(client, engine, "key-0000-0001")
    second = paid_order(client, engine, "key-0000-0002")
    as_user(client, "cust@example.com")
    unpaid = place(client, body(engine, [{"variant_id": variant(engine, "Veg biryani").id, "qty": 1}]), "key-0000-0003").json()
    as_user(client, "chef@example.com")
    board = client.get("/outlets/1/orders").json()
    assert [o["public_code"] for o in board["orders"]] == [first, second]
    assert unpaid["public_code"] not in [o["public_code"] for o in board["orders"]]
    assert board["orders"][0]["lines"][0]["name"] == "Veg biryani"


def test_board_leaves_out_other_outlets_and_closed_orders(client, engine, staff, noon):
    mine = paid_order(client, engine, "key-0000-0001")
    paid_order(client, engine, "key-0000-0002", place_name="Kukatpally")
    as_user(client, "chef@example.com")
    move(client, 1, mine, "cancelled")
    assert client.get("/outlets/1/orders").json()["orders"] == []


# --- moving orders ----------------------------------------------------------------------------


def test_an_order_moves_through_the_kitchen_with_timestamps_and_events(client, engine, staff, noon):
    code = paid_order(client, engine)
    as_user(client, "chef@example.com")
    for status in ["preparing", "ready", "handed_off", "completed"]:
        assert move(client, 1, code, status).status_code == 200
    with Session(engine) as db:
        order = db.scalars(select(Order)).one()
        assert order.status == "completed"
        assert order.preparing_at and order.ready_at and order.completed_at
    assert events(engine)[-4:] == ["order_preparing", "order_ready", "order_handed_off", "order_completed"]


@pytest.mark.parametrize("target", ["ready", "handed_off", "completed"])
def test_stages_cannot_be_skipped(client, engine, staff, noon, target):
    code = paid_order(client, engine)
    as_user(client, "chef@example.com")
    response = move(client, 1, code, target)
    assert response.status_code == 409 and response.json()["detail"]["code"] == "illegal_move"


def test_cancel_is_allowed_early_and_not_once_ready(client, engine, staff, noon):
    early = paid_order(client, engine, "key-0000-0001")
    late = paid_order(client, engine, "key-0000-0002")
    as_user(client, "chef@example.com")
    assert move(client, 1, early, "cancelled").status_code == 200
    move(client, 1, late, "preparing"), move(client, 1, late, "ready")
    assert move(client, 1, late, "cancelled").status_code == 409


def test_staff_of_another_outlet_cannot_move_it(client, engine, staff, noon):
    code = paid_order(client, engine)
    as_user(client, "chef3@example.com")
    assert move(client, 1, code, "preparing").status_code == 403
    assert move(client, 3, code, "preparing").status_code == 404  # not that outlet's order


def test_customers_cannot_move_orders_and_bad_statuses_are_rejected(client, engine, staff, noon):
    code = paid_order(client, engine)
    assert move(client, 1, code, "preparing").status_code == 403
    as_user(client, "chef@example.com")
    for status in ["new", "pending_payment", "payment_failed", "nonsense"]:
        assert move(client, 1, code, status).status_code == 422


# --- promise override -------------------------------------------------------------------------


def promise(client, outlet, code, minutes):
    return client.post(f"/outlets/{outlet}/orders/{code}/promise", json={"minutes": minutes})


def test_only_the_outlet_manager_or_admin_can_change_a_promise(client, engine, staff, noon):
    code = paid_order(client, engine)
    as_user(client, "chef@example.com")
    assert promise(client, 1, code, 30).status_code == 403
    as_user(client, "manager3@example.com")
    assert promise(client, 1, code, 30).status_code == 403
    as_user(client, "manager@example.com")
    data = promise(client, 1, code, 30).json()
    assert data["overridden"] is True
    with Session(engine) as db:
        order = db.scalars(select(Order)).one()
        assert order.override_min == 30 and order.override_by_user_id is not None
    assert "promise_overridden" in events(engine)
    as_user(client, "admin@example.com")
    assert promise(client, 1, code, 45).status_code == 200


@pytest.mark.parametrize("minutes", [0, -5, 241])
def test_promise_bounds(client, engine, staff, noon, minutes):
    code = paid_order(client, engine)
    as_user(client, "manager@example.com")
    assert promise(client, 1, code, minutes).status_code == 422


def test_promise_cannot_change_once_the_order_is_ready(client, engine, staff, noon):
    code = paid_order(client, engine)
    as_user(client, "chef@example.com")
    move(client, 1, code, "preparing"), move(client, 1, code, "ready")
    as_user(client, "manager@example.com")
    assert promise(client, 1, code, 30).status_code == 409


# --- late orders ------------------------------------------------------------------------------


def set_promise(engine, delta_minutes):
    with Session(engine) as db:
        order = db.scalars(select(Order)).one()
        order.promised_at = utcnow() + timedelta(minutes=delta_minutes)
        db.commit()


def test_late_alert_fires_once_after_the_threshold(client, engine, staff, noon):
    paid_order(client, engine)
    now = utcnow()
    with Session(engine) as db:
        order = db.scalars(select(Order)).one()
        order.promised_at = now - timedelta(minutes=LATE_ALERT_MINUTES)  # exactly 10 late: not yet
        db.commit()
        assert sweep_late_orders(db, now) == []
        order.promised_at = now - timedelta(minutes=LATE_ALERT_MINUTES + 1)
        db.commit()
        assert [o.id for o in sweep_late_orders(db, now)] == [order.id]
        assert sweep_late_orders(db, now) == []  # only once
    assert events(engine).count("order_late") == 1


def test_a_ready_but_uncollected_order_still_counts_and_finished_ones_do_not(client, engine, staff, noon):
    ready, done = paid_order(client, engine, "key-0000-0001"), paid_order(client, engine, "key-0000-0002")
    as_user(client, "chef@example.com")
    move(client, 1, ready, "preparing"), move(client, 1, ready, "ready")
    for s in ["preparing", "ready", "handed_off", "completed"]:
        move(client, 1, done, s)
    now = utcnow()
    with Session(engine) as db:
        for order in db.scalars(select(Order)):
            order.promised_at = now - timedelta(minutes=30)
        db.commit()
        assert [o.public_code for o in sweep_late_orders(db, now)] == [ready]


def test_board_reports_minutes_late_and_an_override_restarts_the_clock(client, engine, staff, noon):
    code = paid_order(client, engine)
    set_promise(engine, -30)
    as_user(client, "chef@example.com")
    row = client.get("/outlets/1/orders").json()["orders"][0]
    assert row["minutes_late"] >= 29 and row["late_alerted"] is True
    as_user(client, "manager@example.com")
    promise(client, 1, code, 20)
    row = client.get("/outlets/1/orders").json()["orders"][0]
    assert row["minutes_late"] == 0 and row["late_alerted"] is False


# --- pausing dishes ---------------------------------------------------------------------------


def availability(client, outlet, item_id, flag):
    return client.put(f"/outlets/{outlet}/items/{item_id}/availability", json={"is_available": flag})


def test_kitchen_can_pause_and_resume_a_dish_and_customers_feel_it(client, engine, staff, noon):
    v = variant(engine, "Veg biryani")
    as_user(client, "chef@example.com")
    assert availability(client, 1, v.item_id, False).json() == {"item_id": v.item_id, "is_available": False}
    as_user(client, "cust@example.com")
    paused = place(client, body(engine, [{"variant_id": v.id, "qty": 1}]), "key-0000-0009").json()
    assert paused["outlet"]["name"] == "Gachibowli cloud kitchen" and paused["rerouted_from"] == "Kondapur"
    as_user(client, "chef@example.com")
    availability(client, 1, v.item_id, True)
    as_user(client, "cust@example.com")
    again = place(client, body(engine, [{"variant_id": v.id, "qty": 1}]), "key-0000-0010").json()
    assert again["outlet"]["name"] == "Kondapur"


def test_availability_is_limited_to_own_outlet_and_listed_dishes(client, engine, staff, noon):
    v = variant(engine, "Veg biryani")
    chai = variant(engine, "Irani chai", "Cup")
    as_user(client, "chef3@example.com")
    assert availability(client, 1, v.item_id, False).status_code == 403
    as_user(client, "cust@example.com")
    assert availability(client, 1, v.item_id, False).status_code == 403
    as_user(client, "admin@example.com")
    assert availability(client, 2, chai.item_id, False).status_code == 404  # Gachibowli does not offer chai
    assert client.put("/outlets/1/items/1/availability", json={"is_available": "x"}).status_code == 422
