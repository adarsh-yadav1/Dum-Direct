"""Prep-time estimate and the delivery promise.

The model is a small formula anyone on the team can read and challenge, not a black box:

    prep = (base + queue_wait) * bias

- base: the longest base prep time among the dishes in the order (dishes cook in parallel).
- queue_wait: minutes to clear the work already in the kitchen, at the outlet's capacity.
  Work is measured in load units, quantity times the portion's `serves` (assumption A10).
  It is capped, so a huge backlog cannot produce an absurd promise.
- bias: how this outlet has really performed lately. It is the average of actual time to ready
  divided by the estimate over the last completed orders, clamped to a safe range, and 1.0
  until there is enough history.

The promise to the customer adds travel and respects the outlet's own minimum:

    promised = placed + max(prep, outlet minimum) + ceil(distance * minutes per km)

A manager can override the promise (see access rules). Everything here is pure; the database
wrapper only gathers the inputs.
"""

import math
from collections.abc import Sequence
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ItemVariant, MenuItem, Order, OrderItem, Outlet
from app.models.enums import OrderStatus

MAX_QUEUE_WAIT_MINUTES = 90.0
BIAS_MIN, BIAS_MAX = 0.8, 1.5
BIAS_MIN_SAMPLES = 5
BIAS_WINDOW = 20


def queue_wait_minutes(queue_units: float, capacity_units_per_hour: int) -> float:
    return min(MAX_QUEUE_WAIT_MINUTES, max(0.0, queue_units) / capacity_units_per_hour * 60)


def bias_from_history(ratios: Sequence[float]) -> float:
    """Average of actual/estimated over recent orders, clamped. 1.0 when history is too thin."""
    if len(ratios) < BIAS_MIN_SAMPLES:
        return 1.0
    return min(BIAS_MAX, max(BIAS_MIN, sum(ratios) / len(ratios)))


def estimate_prep_minutes(base_minutes: float, queue_units: float, capacity_units_per_hour: int, bias: float) -> int:
    wait = queue_wait_minutes(queue_units, capacity_units_per_hour)
    return math.ceil((base_minutes + wait) * bias)


def promised_minutes(prep_minutes: int, outlet_min_prep: int, distance_km: float, minutes_per_km: float) -> int:
    return max(prep_minutes, outlet_min_prep) + math.ceil(distance_km * minutes_per_km)


# --- inputs from the database ---------------------------------------------------------------


def queue_units(db: Session, outlet_id: int, exclude_order_id: int) -> float:
    """Load units of the orders the kitchen is still working on, not counting this one."""
    query = (
        select(func.coalesce(func.sum(OrderItem.qty * ItemVariant.serves), 0))
        .join(ItemVariant, ItemVariant.id == OrderItem.variant_id)
        .join(Order, Order.id == OrderItem.order_id)
        .where(
            Order.outlet_id == outlet_id,
            Order.status.in_([OrderStatus.NEW.value, OrderStatus.PREPARING.value]),
            Order.id != exclude_order_id,
        )
    )
    return float(db.scalar(query) or 0)


def outlet_bias(db: Session, outlet_id: int) -> float:
    rows = db.execute(
        select(Order.placed_at, Order.ready_at, Order.ai_estimate_min)
        .where(
            Order.outlet_id == outlet_id,
            Order.ready_at.is_not(None),
            Order.ai_estimate_min.is_not(None),
            Order.status.in_([OrderStatus.READY.value, OrderStatus.HANDED_OFF.value, OrderStatus.COMPLETED.value]),
        )
        .order_by(Order.ready_at.desc())
        .limit(BIAS_WINDOW)
    ).all()
    ratios = []
    for placed, ready, estimate in rows:
        actual = (ready - placed).total_seconds() / 60
        if estimate > 0 and actual > 0:
            ratios.append(actual / estimate)
    return bias_from_history(ratios)


def estimate_order(db: Session, order: Order, outlet: Outlet, now: datetime, minutes_per_km: float) -> tuple[int, datetime]:
    """Prep estimate (minutes) and promised time for an order that has just entered the queue."""
    base = db.scalar(
        select(func.max(MenuItem.base_prep_minutes))
        .join(OrderItem, OrderItem.item_id == MenuItem.id)
        .where(OrderItem.order_id == order.id)
    ) or 0
    waiting = queue_units(db, outlet.id, order.id)
    prep = estimate_prep_minutes(base, waiting, outlet.capacity_units_per_hour, outlet_bias(db, outlet.id))
    total = promised_minutes(prep, outlet.min_prep_minutes, order.distance_km or 0.0, minutes_per_km)
    return prep, now + timedelta(minutes=total)
