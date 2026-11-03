"""Demo accounts and the three sample orders from the client brief.

All people are invented and use the reserved example.com domain. Order times are
shifted so each order looks current at the moment of seeding, while keeping its
own placed-to-promised duration and status from the brief's sample table.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import clock_time_ist
from app.core.security import hash_password
from app.models import (
    ItemVariant,
    Locality,
    MenuItem,
    Notification,
    Order,
    OrderEvent,
    OrderItem,
    Outlet,
    Payment,
    User,
)
from app.services.geo import haversine_km
from app.services.pricing import gst_included_paise

# (email, name, role, outlet name, gave marketing consent)
DEMO_USERS: list[tuple[str, str, str, str | None, bool]] = [
    ("ananya@example.com", "Ananya Rao", "customer", None, True),
    ("rahul@example.com", "Rahul Verma", "customer", None, False),
    ("kitchen.kondapur@example.com", "Kondapur Kitchen", "kitchen", "Kondapur", False),
    (
        "kitchen.gachibowli@example.com",
        "Gachibowli Kitchen",
        "kitchen",
        "Gachibowli cloud kitchen",
        False,
    ),
    ("kitchen.kukatpally@example.com", "Kukatpally Kitchen", "kitchen", "Kukatpally", False),
    ("manager.kukatpally@example.com", "Kukatpally Manager", "manager", "Kukatpally", False),
    ("admin@example.com", "Menu Admin", "admin", None, False),
]

# Delivery points sit slightly off a locality's centre so distances are never exactly zero.
DELIVERY_OFFSET = (0.006, 0.004)


@dataclass(frozen=True)
class SampleOrder:
    code: str
    outlet: str
    customer: str  # email
    lines: tuple[tuple[str, str, int], ...]  # (item, portion, quantity)
    payment_method: str
    status: str  # "preparing" or "ready"
    delivery_locality: str
    minutes_since_placed: int  # shifts the order to look current
    promised_after_minutes: int  # placed -> promised, from the brief's sample table
    ready_minutes_ago: int | None = None


# Brief's table: promised minus placed is 45, 40 and 50 minutes. The third order is
# placed 54 minutes ago, so its promise passed 4 minutes ago ("Late by 4 minutes").
SAMPLE_ORDERS: list[SampleOrder] = [
    SampleOrder(
        "WEB-778120", "Kondapur", "ananya@example.com",
        (("Chicken dum biryani", "Family pack", 1), ("Double ka meetha", "Regular", 2)),
        "upi", "preparing", "HITEC City",
        minutes_since_placed=12, promised_after_minutes=45,
    ),
    SampleOrder(
        "WEB-778131", "Gachibowli cloud kitchen", "rahul@example.com",
        (("Veg biryani", "Regular", 2), ("Mirchi ka salan", "Regular", 1)),
        "card", "ready", "Financial District",
        minutes_since_placed=32, promised_after_minutes=40, ready_minutes_ago=2,
    ),
    SampleOrder(
        "WEB-778146", "Kukatpally", "ananya@example.com",
        (("Mutton haleem", "Regular", 3),),
        "upi", "preparing", "Kukatpally",
        minutes_since_placed=54, promised_after_minutes=50,
    ),
]


def seed_users(db: Session, now: datetime, password: str) -> dict[str, User]:
    outlets = {outlet.name: outlet for outlet in db.scalars(select(Outlet))}
    users: dict[str, User] = {}
    for email, name, role, outlet_name, consented in DEMO_USERS:
        users[email] = User(
            email=email,
            name=name,
            role=role,
            outlet_id=outlets[outlet_name].id if outlet_name else None,
            password_hash=hash_password(password),
            marketing_opt_in=consented,
            marketing_opt_in_at=now if consented else None,
        )
    db.add_all(users.values())
    db.flush()
    return users


def _routing_decision(db: Session, spec: SampleOrder, lat: float, lng: float) -> dict:
    """Which outlets cover the delivery point, nearest first, using the same rule as routing."""
    candidates = []
    for outlet in db.scalars(select(Outlet)):
        distance = haversine_km(lat, lng, outlet.latitude, outlet.longitude)
        if outlet.is_open and distance <= outlet.delivery_radius_km:
            candidates.append({"outlet": outlet.name, "distance_km": round(distance, 2)})
    candidates.sort(key=lambda candidate: candidate["distance_km"])
    if not candidates or candidates[0]["outlet"] != spec.outlet:
        raise ValueError(f"{spec.code}: seed data disagrees with the nearest-outlet rule")
    return {
        "chosen": spec.outlet,
        "reason": "nearest open outlet whose delivery radius covers the address (seeded sample order)",
        "candidates": candidates,
    }


def seed_orders(db: Session, now: datetime, users: dict[str, User]) -> None:
    outlets = {outlet.name: outlet for outlet in db.scalars(select(Outlet))}

    for spec in SAMPLE_ORDERS:
        outlet = outlets[spec.outlet]
        place = db.scalars(select(Locality).where(Locality.name == spec.delivery_locality)).one()
        lat, lng = place.latitude + DELIVERY_OFFSET[0], place.longitude + DELIVERY_OFFSET[1]
        routing = _routing_decision(db, spec, lat, lng)

        placed_at = now - timedelta(minutes=spec.minutes_since_placed)
        promised_at = placed_at + timedelta(minutes=spec.promised_after_minutes)
        preparing_at = placed_at + timedelta(minutes=3)
        ready_at = now - timedelta(minutes=spec.ready_minutes_ago) if spec.ready_minutes_ago else None

        items = []
        for item_name, portion, qty in spec.lines:
            variant = db.scalars(
                select(ItemVariant)
                .join(MenuItem)
                .where(MenuItem.name == item_name, ItemVariant.label == portion)
            ).one()
            items.append(
                OrderItem(
                    item_id=variant.item_id,
                    variant_id=variant.id,
                    name_snapshot=item_name,
                    variant_label_snapshot=portion,
                    unit_price_paise=variant.price_paise,
                    qty=qty,
                    addons_json=[],
                )
            )
        subtotal = sum(line.unit_price_paise * line.qty for line in items)
        customer = users[spec.customer]

        order = Order(
            public_code=spec.code,
            user_id=customer.id,
            outlet_id=outlet.id,
            status=spec.status,
            delivery_latitude=lat,
            delivery_longitude=lng,
            address_json={"line": f"Sample address near {spec.delivery_locality}"},
            distance_km=routing["candidates"][0]["distance_km"],
            routing_json=routing,
            subtotal_paise=subtotal,
            discount_paise=0,
            delivery_fee_paise=outlet.delivery_fee_paise,
            total_paise=subtotal + outlet.delivery_fee_paise,
            gst_included_paise=gst_included_paise(subtotal + outlet.delivery_fee_paise),
            placed_at=placed_at,
            promised_at=promised_at,
            preparing_at=preparing_at,
            ready_at=ready_at,
            items=items,
            payments=[
                Payment(
                    method=spec.payment_method,
                    status="succeeded",
                    provider_ref=f"mock_{spec.code}",
                    amount_paise=subtotal + outlet.delivery_fee_paise,
                )
            ],
        )
        db.add(order)
        db.flush()

        timeline = [
            ("order_placed", placed_at, {"total_paise": order.total_paise}),
            ("payment_succeeded", placed_at + timedelta(seconds=10), {"status": "new"}),
            ("status_changed", preparing_at, {"from": "new", "to": "preparing"}),
        ]
        if ready_at:
            timeline.append(("status_changed", ready_at, {"from": "preparing", "to": "ready"}))
        db.add_all(
            OrderEvent(
                order_id=order.id,
                outlet_id=outlet.id,
                type=kind,
                payload_json=payload,
                created_at=when,
            )
            for kind, when, payload in timeline
        )
        # Messages are only recorded, never sent (assumption A9).
        db.add(
            Notification(
                user_id=customer.id,
                order_id=order.id,
                channel="whatsapp",
                template="order_confirmed",
                body=f"Your order {spec.code} is confirmed. Promised by {clock_time_ist(promised_at)}.",
            )
        )
    db.flush()
