"""The database must reject invalid data on its own, whatever the application code does."""

from datetime import time

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, CityPrice, MenuItem, Order, OrderEvent, Outlet, User
from tests.factories import make_item, make_order, make_outlet, make_user, order_values


def assert_rejected(db: Session, *rows: object) -> None:
    """Assert the database refuses these rows, keeping everything saved before them."""
    db.commit()  # a rollback below must only discard the rejected rows
    with pytest.raises(IntegrityError):
        db.add_all(rows)
        db.flush()
    db.rollback()


# ----- users -----------------------------------------------------------------


def test_kitchen_user_must_belong_to_an_outlet(session: Session):
    assert_rejected(
        session,
        User(email="k@example.com", password_hash="x", name="Kitchen", role="kitchen"),
    )


def test_customer_cannot_belong_to_an_outlet(session: Session):
    outlet = make_outlet(session)
    assert_rejected(
        session,
        User(
            email="c@example.com",
            password_hash="x",
            name="Customer",
            role="customer",
            outlet_id=outlet.id,
        ),
    )


def test_staff_user_with_outlet_is_accepted(session: Session):
    outlet = make_outlet(session)
    user = make_user(session, email="k@example.com", role="kitchen", outlet_id=outlet.id)
    assert user.id is not None


def test_unknown_role_is_rejected(session: Session):
    assert_rejected(
        session, User(email="x@example.com", password_hash="x", name="X", role="superuser")
    )


def test_email_must_be_lowercase_and_unique(session: Session):
    assert_rejected(
        session, User(email="Mixed@Example.com", password_hash="x", name="X", role="customer")
    )
    make_user(session, email="same@example.com")
    assert_rejected(
        session, User(email="same@example.com", password_hash="x", name="Y", role="customer")
    )


# ----- outlets ---------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"fssai_no": "123"},  # must be 14 characters
        {"delivery_radius_km": 0},
        {"latitude": 91.0},
        {"longitude": -181.0},
        {"min_prep_minutes": 0},
        {"capacity_units_per_hour": 0},
        {"delivery_fee_paise": -1},
        {"kind": "food_truck"},
    ],
)
def test_outlet_rejects_invalid_values(session: Session, overrides):
    values = {
        "name": "Bad Outlet",
        "kind": "outlet",
        "city": "Hyderabad",
        "locality": "X",
        "address_line": "Y",
        "latitude": 17.4,
        "longitude": 78.4,
        "delivery_radius_km": 5.0,
        "fssai_no": "99999000000101",
        "min_prep_minutes": 20,
        "capacity_units_per_hour": 60,
    }
    values.update(overrides)
    assert_rejected(session, Outlet(**values))


# ----- menu ------------------------------------------------------------------


def test_item_needs_an_existing_category(session: Session):
    assert_rejected(
        session,
        MenuItem(
            category_id=999, slug="ghost", name="Ghost", is_veg=True, base_prep_minutes=5
        ),
    )


def test_spice_level_is_between_zero_and_three(session: Session):
    category = Category(name="Biryani")
    session.add(category)
    session.flush()
    assert_rejected(
        session,
        MenuItem(
            category_id=category.id,
            slug="hot",
            name="Too Hot",
            is_veg=True,
            spice_level=4,
            base_prep_minutes=5,
        ),
    )


def test_category_window_must_be_complete_and_ordered(session: Session):
    assert_rejected(session, Category(name="Half window", available_from=time(16, 0)))
    assert_rejected(
        session,
        Category(name="Backwards", available_from=time(23, 0), available_to=time(16, 0)),
    )
    session.add(Category(name="Evening", available_from=time(16, 0), available_to=time(23, 30)))
    session.flush()


def test_city_price_is_unique_per_variant_and_city(session: Session):
    variant = make_item(session)
    session.add(CityPrice(variant_id=variant.id, city="Bengaluru", price_paise=27500))
    session.flush()
    assert_rejected(session, CityPrice(variant_id=variant.id, city="Bengaluru", price_paise=28000))
    session.add(CityPrice(variant_id=variant.id, city="Chennai", price_paise=26000))
    session.flush()


# ----- orders ----------------------------------------------------------------


def test_order_total_must_equal_its_components(session: Session):
    user, outlet = make_user(session), make_outlet(session)
    assert_rejected(session, Order(**order_values(user, outlet, total_paise=99999)))
    make_order(
        session,
        user,
        outlet,
        public_code="WEB-000002",
        subtotal_paise=100000,
        discount_paise=10000,
        delivery_fee_paise=2000,
        total_paise=92000,
    )


def test_discount_cannot_exceed_subtotal(session: Session):
    user, outlet = make_user(session), make_outlet(session)
    assert_rejected(
        session,
        Order(**order_values(user, outlet, discount_paise=150000, total_paise=-50000)),
    )


def test_order_status_must_be_known(session: Session):
    user, outlet = make_user(session), make_outlet(session)
    assert_rejected(session, Order(**order_values(user, outlet, status="teleported")))


def test_public_code_is_unique(session: Session):
    user, outlet = make_user(session), make_outlet(session)
    make_order(session, user, outlet)
    assert_rejected(session, Order(**order_values(user, outlet)))


def test_idempotency_key_is_unique_per_customer_only(session: Session):
    outlet = make_outlet(session)
    first = make_user(session, email="a@example.com")
    second = make_user(session, email="b@example.com")
    make_order(session, first, outlet, public_code="WEB-1", idempotency_key="key-1")
    # The same customer repeating the key is rejected...
    assert_rejected(
        session,
        Order(**order_values(first, outlet, public_code="WEB-2", idempotency_key="key-1")),
    )
    # ...but another customer may use the same string.
    make_order(session, second, outlet, public_code="WEB-3", idempotency_key="key-1")


def test_override_minutes_must_be_positive(session: Session):
    user, outlet = make_user(session), make_outlet(session)
    assert_rejected(session, Order(**order_values(user, outlet, override_min=0)))


def test_events_get_increasing_ids(session: Session):
    user, outlet = make_user(session), make_outlet(session)
    order = make_order(session, user, outlet)
    events = [
        OrderEvent(order_id=order.id, outlet_id=outlet.id, type=kind, payload_json={})
        for kind in ("order_placed", "payment_succeeded", "status_changed")
    ]
    session.add_all(events)
    session.flush()
    ids = [event.id for event in events]
    assert ids == sorted(ids) and len(set(ids)) == 3
