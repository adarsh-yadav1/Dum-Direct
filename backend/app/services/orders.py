"""Placing an order.

Everything that matters is decided here, on the server, from the database:
- Prices come from the menu (city price where one exists), never from the request.
- The outlet comes from the routing rule, never from the request.
- Dishes must be offered and unpaused at that outlet, and their category must be inside its
  daily window right now.
- A repeated submit with the same idempotency key returns the first order instead of a second.
"""

import secrets
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models import Addon, ItemVariant, MenuItem, Order, OrderEvent, OrderItem, User
from app.models.enums import OrderStatus
from app.schemas.orders import OrderCreate
from app.services.menu import city_prices, effective_price_paise, in_window
from app.services.pricing import gst_included_paise
from app.services.routing import NOT_SERVICEABLE, UNAVAILABLE_ITEMS, assign_outlet


@dataclass
class OrderError(Exception):
    status_code: int
    code: str
    message: str
    item_ids: list[int] = field(default_factory=list)

    def detail(self) -> dict:
        body: dict = {"code": self.code, "message": self.message}
        if self.item_ids:
            body["item_ids"] = self.item_ids
        return body


def _new_public_code(db: Session) -> str:
    for _ in range(10):
        code = f"WEB-{secrets.randbelow(900_000) + 100_000}"
        if db.scalar(select(Order.id).where(Order.public_code == code)) is None:
            return code
    raise RuntimeError("could not allocate an order code")


def find_by_key(db: Session, user: User, key: str) -> Order | None:
    return db.scalar(select(Order).where(Order.user_id == user.id, Order.idempotency_key == key))


def create_order(
    db: Session, user: User, request: OrderCreate, idempotency_key: str, now: datetime
) -> tuple[Order, bool]:
    """Returns the order and whether it was newly created (False for a replay)."""
    existing = find_by_key(db, user, idempotency_key)
    if existing is not None:
        return existing, False

    variant_ids = {line.variant_id for line in request.lines}
    variants = {
        v.id: v
        for v in db.scalars(
            select(ItemVariant)
            .where(ItemVariant.id.in_(variant_ids))
            .options(selectinload(ItemVariant.item).selectinload(MenuItem.category))
        )
    }
    bad = sorted(vid for vid in variant_ids if vid not in variants or not variants[vid].item.is_active)
    if bad:
        raise OrderError(422, "unknown_dish", "Some dishes are not on the menu.", bad)

    addon_ids = {a for line in request.lines for a in line.addon_ids}
    addons = {a.id: a for a in db.scalars(select(Addon).where(Addon.id.in_(addon_ids)))} if addon_ids else {}
    for line in request.lines:
        item_id = variants[line.variant_id].item_id
        for addon_id in line.addon_ids:
            addon = addons.get(addon_id)
            if addon is None or addon.item_id != item_id or not addon.is_active:
                raise OrderError(422, "invalid_addon", "An add-on does not belong to that dish.")

    item_ids = {v.item_id for v in variants.values()}
    decision = assign_outlet(db, request.latitude, request.longitude, item_ids)
    if decision.status == NOT_SERVICEABLE or decision.chosen is None:
        raise OrderError(422, "not_serviceable", "We do not deliver to this address yet.")
    if decision.status == UNAVAILABLE_ITEMS:
        raise OrderError(
            409,
            "items_unavailable",
            "Some dishes are not available right now.",
            decision.unavailable_item_ids,
        )
    outlet, distance = decision.chosen.outlet, decision.chosen.distance_km

    closed = sorted(
        item_id
        for item_id in item_ids
        if not in_window(next(v.item.category for v in variants.values() if v.item_id == item_id), now)
    )
    if closed:
        raise OrderError(409, "not_orderable_now", "Some dishes are not served at this time.", closed)

    overrides = city_prices(db, outlet.city)
    order_items = []
    for line in request.lines:
        variant = variants[line.variant_id]
        chosen_addons = [addons[a] for a in line.addon_ids]
        unit = effective_price_paise(variant.price_paise, variant.id, overrides) + sum(
            a.price_paise for a in chosen_addons
        )
        order_items.append(
            OrderItem(
                item_id=variant.item_id,
                variant_id=variant.id,
                name_snapshot=variant.item.name,
                variant_label_snapshot=variant.label,
                unit_price_paise=unit,
                qty=line.qty,
                addons_json=[{"name": a.name, "price_paise": a.price_paise} for a in chosen_addons],
                notes=line.notes,
            )
        )
    subtotal = sum(i.unit_price_paise * i.qty for i in order_items)
    fee = outlet.delivery_fee_paise
    total = subtotal + fee

    order = Order(
        public_code=_new_public_code(db),
        user_id=user.id,
        outlet_id=outlet.id,
        status=OrderStatus.PENDING_PAYMENT.value,
        delivery_latitude=request.latitude,
        delivery_longitude=request.longitude,
        address_json={"line": request.address_line, "landmark": request.landmark},
        distance_km=round(distance, 2),
        routing_json=decision.to_json(),
        subtotal_paise=subtotal,
        discount_paise=0,
        delivery_fee_paise=fee,
        total_paise=total,
        gst_included_paise=gst_included_paise(total),
        placed_at=now,
        idempotency_key=idempotency_key,
        items=order_items,
    )
    db.add(order)
    db.flush()
    db.add(
        OrderEvent(
            order_id=order.id,
            outlet_id=outlet.id,
            type="order_created",
            payload_json={"public_code": order.public_code, "total_paise": total},
            actor_user_id=user.id,
        )
    )
    try:
        db.commit()
    except IntegrityError:  # the same key arrived twice at once; the first one won
        db.rollback()
        winner = find_by_key(db, user, idempotency_key)
        if winner is None:
            raise
        return winner, False
    return order, True
