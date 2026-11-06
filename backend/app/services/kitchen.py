"""What outlet staff do with orders: see the board, move orders along, override a promise, flag late ones.

Who may do each thing is decided by the API layer using services/access.py; this module only
enforces the order rules (legal moves, timestamps, one event per change).
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, MenuItem, Order, OrderEvent, OutletItem
from app.models.enums import OrderStatus
from app.services.order_state import OPEN_STATUSES, can_kitchen_move

# The board also keeps an order out with the rider until delivery is confirmed.
BOARD_STATUSES = frozenset({*OPEN_STATUSES, OrderStatus.HANDED_OFF})

LATE_ALERT_MINUTES = 10
_STAMP = {
    OrderStatus.PREPARING.value: "preparing_at",
    OrderStatus.READY.value: "ready_at",
    OrderStatus.COMPLETED.value: "completed_at",
}


class KitchenError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code, self.code, self.message = status_code, code, message


def open_orders(db: Session, outlet_id: int) -> list[Order]:
    """Orders still on the board (cooking, ready, or out for delivery), oldest first."""
    return list(
        db.scalars(
            select(Order)
            .where(Order.outlet_id == outlet_id, Order.status.in_([s.value for s in BOARD_STATUSES]))
            .order_by(Order.placed_at, Order.id)
        )
    )


def outlet_order(db: Session, outlet_id: int, code: str) -> Order:
    """An order of this outlet. One that belongs to another outlet is reported as missing."""
    order = db.scalar(select(Order).where(Order.public_code == code, Order.outlet_id == outlet_id).with_for_update())
    if order is None:
        raise KitchenError(404, "order_not_found", "Order not found.")
    return order


def _event(db: Session, order: Order, type_: str, actor_id: int, payload: dict) -> None:
    db.add(OrderEvent(order_id=order.id, outlet_id=order.outlet_id, type=type_, payload_json=payload, actor_user_id=actor_id))


def move_order(db: Session, order: Order, target: str, actor_id: int, now: datetime) -> Order:
    if not can_kitchen_move(order.status, target):
        raise KitchenError(409, "illegal_move", f"An order that is {order.status} cannot become {target}.")
    previous = order.status
    order.status = target
    if target in _STAMP:
        setattr(order, _STAMP[target], now)
    _event(db, order, f"order_{target}", actor_id, {"from": previous, "to": target})
    db.commit()
    return order


def override_promise(db: Session, order: Order, minutes: int, actor_id: int, now: datetime) -> Order:
    """Set the promised time to `minutes` from now. Only an order still being prepared can change."""
    if order.status not in (OrderStatus.NEW.value, OrderStatus.PREPARING.value):
        raise KitchenError(409, "not_changeable", "The promised time can only change while the order is new or being prepared.")
    previous = order.promised_at
    order.promised_at = now + timedelta(minutes=minutes)
    order.override_min, order.override_by_user_id = minutes, actor_id
    order.late_alerted_at = None  # a fresh promise starts a fresh clock
    _event(db, order, "promise_overridden", actor_id,
           {"minutes_from_now": minutes, "promised_at": order.promised_at.isoformat(),
            "previous": previous.isoformat() if previous else None})
    db.commit()
    return order


def minutes_late(order: Order, now: datetime) -> int:
    if order.promised_at is None:
        return 0
    promised = order.promised_at if order.promised_at.tzinfo else order.promised_at.replace(tzinfo=now.tzinfo)
    return max(0, int((now - promised).total_seconds() // 60))


def sweep_late_orders(db: Session, now: datetime) -> list[Order]:
    """Flag each open order that is more than LATE_ALERT_MINUTES past its promise. Once per order."""
    flagged = []
    candidates = db.scalars(
        select(Order).where(
            Order.status.in_([s.value for s in OPEN_STATUSES]),
            Order.promised_at.is_not(None),
            Order.late_alerted_at.is_(None),
        )
    )
    for order in candidates:
        late = minutes_late(order, now)
        if late > LATE_ALERT_MINUTES:
            order.late_alerted_at = now
            _event(db, order, "order_late", None, {"minutes_late": late})
            flagged.append(order)
    if flagged:
        db.commit()
    return flagged


def set_availability(db: Session, outlet_id: int, item_id: int, available: bool, actor_id: int) -> OutletItem:
    row = db.get(OutletItem, (outlet_id, item_id))
    if row is None:
        raise KitchenError(404, "item_not_offered", "This outlet does not offer that dish.")
    row.is_available, row.updated_by_user_id = available, actor_id
    db.commit()
    return row


def outlet_dishes(db: Session, outlet_id: int) -> list[dict]:
    """The dishes this outlet lists, with whether each can be ordered now, for the pause switches."""
    rows = db.execute(
        select(MenuItem.id, MenuItem.name, Category.name, OutletItem.is_available)
        .join(OutletItem, OutletItem.item_id == MenuItem.id)
        .join(Category, Category.id == MenuItem.category_id)
        .where(OutletItem.outlet_id == outlet_id, MenuItem.is_active.is_(True))
        .order_by(Category.sort_order, MenuItem.name)
    )
    return [{"item_id": i, "name": n, "category": c, "is_available": a} for i, n, c, a in rows]
