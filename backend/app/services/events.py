"""Reading the order event log for the live streams and the polling fallback.

The log's increasing id is the cursor: a client that remembers the last id it saw can ask for
everything after it, so a dropped connection never loses or repeats an update. Kitchen staff
see every event of their outlet; a customer sees only the milestones of their own order, with
nothing about staff.
"""

import json
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.clock import as_utc
from app.models import Order, OrderEvent

PAGE_SIZE = 100

# What a customer may see, and which payload fields go with it.
CUSTOMER_EVENTS: dict[str, tuple[str, ...]] = {
    "order_created": (),
    "payment_succeeded": (),
    "payment_failed": (),
    "order_new": ("promised_at",),
    "order_preparing": (),
    "order_ready": (),
    "order_handed_off": (),
    "order_completed": (),
    "order_cancelled": (),
    "promise_overridden": ("promised_at",),
}


def latest_event_id(db: Session, *, outlet_id: int | None = None, order_id: int | None = None) -> int:
    query = select(func.coalesce(func.max(OrderEvent.id), 0))
    if outlet_id is not None:
        query = query.where(OrderEvent.outlet_id == outlet_id)
    if order_id is not None:
        query = query.where(OrderEvent.order_id == order_id)
    return int(db.scalar(query))


def events_after(
    db: Session, after: int, *, outlet_id: int | None = None, order_id: int | None = None, customer: bool = False
) -> list[dict]:
    """Up to PAGE_SIZE events with an id above `after`, oldest first, in the form sent to clients."""
    query = (
        select(OrderEvent, Order.public_code)
        .join(Order, Order.id == OrderEvent.order_id)
        .where(OrderEvent.id > after)
        .order_by(OrderEvent.id)
        .limit(PAGE_SIZE)
    )
    if outlet_id is not None:
        query = query.where(OrderEvent.outlet_id == outlet_id)
    if order_id is not None:
        query = query.where(OrderEvent.order_id == order_id)
    if customer:
        query = query.where(OrderEvent.type.in_(CUSTOMER_EVENTS))
    return [to_wire(event, code, customer) for event, code in db.execute(query)]


def to_wire(event: OrderEvent, public_code: str, customer: bool) -> dict:
    payload = event.payload_json or {}
    if customer:
        payload = {k: payload[k] for k in CUSTOMER_EVENTS.get(event.type, ()) if k in payload}
    return {
        "id": event.id,
        "type": event.type,
        "order": public_code,
        "at": as_utc(event.created_at).isoformat(),
        "data": payload,
    }


def format_sse(event: dict) -> str:
    """One Server-Sent Event. The id lets the browser send Last-Event-ID when it reconnects."""
    return f"id: {event['id']}\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"


def last_id(events: Iterable[dict], default: int) -> int:
    return max((e["id"] for e in events), default=default)
