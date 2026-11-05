from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ItemVariant, MenuItem, Order, OrderItem
from app.services.estimator import (
    BIAS_MAX,
    BIAS_MIN,
    MAX_QUEUE_WAIT_MINUTES,
    bias_from_history,
    estimate_prep_minutes,
    outlet_bias,
    promised_minutes,
    queue_units,
    queue_wait_minutes,
)
from tests.factories import make_item, make_order, make_outlet, make_user

T0 = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def test_empty_kitchen_has_no_wait():
    assert queue_wait_minutes(0, 60) == 0


def test_wait_is_queue_over_capacity():
    assert queue_wait_minutes(30, 60) == 30      # 30 units at 60/hour
    assert queue_wait_minutes(15, 30) == 30


def test_wait_is_capped():
    assert queue_wait_minutes(10_000, 60) == MAX_QUEUE_WAIT_MINUTES


def test_estimate_is_base_plus_wait_times_bias_rounded_up():
    assert estimate_prep_minutes(20, 0, 60, 1.0) == 20
    assert estimate_prep_minutes(20, 30, 60, 1.0) == 50
    assert estimate_prep_minutes(20, 0, 60, 1.1) == 22
    assert estimate_prep_minutes(15, 0, 60, 1.05) == 16  # 15.75 rounds up


def test_busier_kitchen_never_gives_a_shorter_estimate():
    values = [estimate_prep_minutes(20, q, 60, 1.0) for q in (0, 10, 20, 40, 80)]
    assert values == sorted(values)


def test_promise_respects_the_outlet_minimum_and_adds_travel():
    assert promised_minutes(12, 20, 0.0, 3) == 20
    assert promised_minutes(25, 20, 3.1, 3) == 25 + 10
    assert promised_minutes(25, 20, 0.0, 3) == 25


def test_bias_needs_enough_history():
    assert bias_from_history([2.0] * 4) == 1.0


def test_bias_is_the_average_ratio_clamped():
    assert bias_from_history([1.2] * 5) == pytest.approx(1.2)
    assert bias_from_history([3.0] * 5) == BIAS_MAX
    assert bias_from_history([0.1] * 5) == BIAS_MIN


# --- database inputs ------------------------------------------------------------------------


def add_line(db: Session, order: Order, name: str, qty: int, serves: int):
    variant = make_item(db, name)
    variant.serves = serves
    db.add(OrderItem(order_id=order.id, item_id=variant.item_id, variant_id=variant.id,
                     name_snapshot=name, variant_label_snapshot="x", unit_price_paise=100, qty=qty, addons_json=[]))
    db.flush()


def test_queue_counts_only_open_work_at_this_outlet_excluding_itself(session: Session):
    outlet, other = make_outlet(session), make_outlet(session, name="Other", fssai_no="99999000000102")
    user = make_user(session)
    me = make_order(session, user, outlet, public_code="WEB-1", status="new")
    new = make_order(session, user, outlet, public_code="WEB-2", status="new")
    prep = make_order(session, user, outlet, public_code="WEB-3", status="preparing")
    done = make_order(session, user, outlet, public_code="WEB-4", status="ready")
    elsewhere = make_order(session, user, other, public_code="WEB-5", status="new")
    for i, order in enumerate([me, new, prep, done, elsewhere]):
        add_line(session, order, f"Dish {i}", qty=2, serves=3)   # 6 units each
    assert queue_units(session, outlet.id, me.id) == 12.0


def test_outlet_bias_uses_actual_over_estimate(session: Session):
    outlet, user = make_outlet(session), make_user(session)
    for i in range(5):  # promised 20 min of prep, took 30 -> ratio 1.5
        make_order(session, user, outlet, public_code=f"WEB-{i}", status="completed", placed_at=T0,
                   ready_at=T0 + timedelta(minutes=30), ai_estimate_min=20)
    assert outlet_bias(session, outlet.id) == pytest.approx(1.5)


def test_bias_ignores_unfinished_orders_and_other_outlets(session: Session):
    outlet, other, user = make_outlet(session), make_outlet(session, name="O", fssai_no="99999000000102"), make_user(session)
    for i in range(5):
        make_order(session, user, other, public_code=f"WEB-{i}", status="completed", placed_at=T0,
                   ready_at=T0 + timedelta(minutes=40), ai_estimate_min=20)
    make_order(session, user, outlet, public_code="WEB-9", status="preparing", placed_at=T0, ai_estimate_min=20)
    assert outlet_bias(session, outlet.id) == 1.0
