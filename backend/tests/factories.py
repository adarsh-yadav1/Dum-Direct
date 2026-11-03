"""Small builders that create valid rows, so each test only states what it is about."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Category, ItemVariant, MenuItem, Order, Outlet, User


def make_outlet(db: Session, **overrides: Any) -> Outlet:
    values: dict[str, Any] = {
        "name": "Test Outlet",
        "kind": "outlet",
        "city": "Hyderabad",
        "locality": "Kondapur",
        "address_line": "1 Test Road",
        "latitude": 17.46,
        "longitude": 78.365,
        "delivery_radius_km": 5.0,
        "fssai_no": "99999000000101",
        "min_prep_minutes": 20,
        "capacity_units_per_hour": 60,
    }
    values.update(overrides)
    outlet = Outlet(**values)
    db.add(outlet)
    db.flush()
    return outlet


def make_user(db: Session, **overrides: Any) -> User:
    values: dict[str, Any] = {
        "email": "customer@example.com",
        "password_hash": "not-a-real-hash",
        "name": "Test Customer",
        "role": "customer",
    }
    values.update(overrides)
    user = User(**values)
    db.add(user)
    db.flush()
    return user


def make_item(db: Session, name: str = "Test Biryani", price_paise: int = 25000) -> ItemVariant:
    category = db.query(Category).first() or Category(name="Biryani")
    db.add(category)
    db.flush()
    item = MenuItem(
        category_id=category.id,
        slug=name.lower().replace(" ", "-"),
        name=name,
        is_veg=False,
        base_prep_minutes=20,
    )
    db.add(item)
    db.flush()
    variant = ItemVariant(item_id=item.id, label="Regular", price_paise=price_paise)
    db.add(variant)
    db.flush()
    return variant


def order_values(user: User, outlet: Outlet, **overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "public_code": "WEB-000001",
        "user_id": user.id,
        "outlet_id": outlet.id,
        "status": "new",
        "delivery_latitude": 17.47,
        "delivery_longitude": 78.37,
        "address_json": {"line": "2 Test Lane"},
        "subtotal_paise": 100000,
        "discount_paise": 0,
        "delivery_fee_paise": 0,
        "total_paise": 100000,
        "gst_included_paise": 4762,
        "placed_at": datetime(2026, 11, 2, 14, 0, tzinfo=UTC),
    }
    values.update(overrides)
    return values


def make_order(db: Session, user: User, outlet: Outlet, **overrides: Any) -> Order:
    order = Order(**order_values(user, outlet, **overrides))
    db.add(order)
    db.flush()
    return order
