from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.clock import as_utc
from app.core.config import get_settings
from app.core.security import verify_password
from app.models import (
    Base,
    Notification,
    Order,
    OrderEvent,
    Outlet,
    Payment,
    User,
)
from app.seed.run import main, reset_database, seed_all
from tests.conftest import make_sqlite_engine

NOW = datetime(2026, 11, 2, 15, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Full-strength Argon2 is deliberately slow; its own tests cover it (test_security.py).

    The hashes made here still verify with the real verify_password.
    """
    cheap = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    monkeypatch.setattr("app.seed.demo.hash_password", cheap.hash)


@pytest.fixture()
def seeded(session: Session) -> Session:
    seed_all(session, now=NOW, password="test-password-1")
    session.commit()
    return session


def order(db: Session, code: str) -> Order:
    return db.scalars(select(Order).where(Order.public_code == code)).one()


def minutes(delta: timedelta) -> float:
    return delta.total_seconds() / 60


# ----- users -----------------------------------------------------------------


def test_demo_accounts_cover_every_role_with_the_right_outlet(seeded: Session):
    users = {user.email: user for user in seeded.scalars(select(User))}
    outlets = {outlet.id: outlet.name for outlet in seeded.scalars(select(Outlet))}

    assert {user.role for user in users.values()} == {"customer", "kitchen", "manager", "admin"}
    assert outlets[users["kitchen.kondapur@example.com"].outlet_id] == "Kondapur"
    assert outlets[users["kitchen.gachibowli@example.com"].outlet_id] == "Gachibowli cloud kitchen"
    assert outlets[users["manager.kukatpally@example.com"].outlet_id] == "Kukatpally"
    assert users["admin@example.com"].outlet_id is None
    assert users["ananya@example.com"].outlet_id is None


def test_demo_passwords_are_hashed_and_verify(seeded: Session):
    for user in seeded.scalars(select(User)):
        assert "test-password-1" not in user.password_hash
        assert verify_password("test-password-1", user.password_hash)
        assert not verify_password("another-password", user.password_hash)


def test_marketing_consent_is_recorded_with_a_time_only_when_given(seeded: Session):
    ananya = seeded.scalars(select(User).where(User.email == "ananya@example.com")).one()
    rahul = seeded.scalars(select(User).where(User.email == "rahul@example.com")).one()
    assert ananya.marketing_opt_in and as_utc(ananya.marketing_opt_in_at) == NOW
    assert not rahul.marketing_opt_in and rahul.marketing_opt_in_at is None


# ----- sample orders ---------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "outlet", "total", "gst", "status", "payment"),
    [
        ("WEB-778120", "Kondapur", 118_000, 5_619, "preparing", "upi"),
        ("WEB-778131", "Gachibowli cloud kitchen", 64_000, 3_048, "ready", "card"),
        ("WEB-778146", "Kukatpally", 105_000, 5_000, "preparing", "upi"),
    ],
)
def test_sample_orders_match_the_brief(
    seeded: Session, code: str, outlet: str, total: int, gst: int, status: str, payment: str
):
    row = order(seeded, code)
    assert seeded.get(Outlet, row.outlet_id).name == outlet
    assert (row.total_paise, row.gst_included_paise, row.status) == (total, gst, status)
    assert row.total_paise == sum(line.unit_price_paise * line.qty for line in row.items)
    assert [p.method for p in row.payments] == [payment]
    assert row.payments[0].status == "succeeded"
    assert row.payments[0].amount_paise == total


def test_each_order_keeps_its_own_promised_duration_from_the_brief(seeded: Session):
    durations = {
        code: minutes(as_utc(order(seeded, code).promised_at) - as_utc(order(seeded, code).placed_at))
        for code in ("WEB-778120", "WEB-778131", "WEB-778146")
    }
    assert durations == {"WEB-778120": 45, "WEB-778131": 40, "WEB-778146": 50}


def test_the_kukatpally_order_is_late_by_exactly_four_minutes(seeded: Session):
    late = order(seeded, "WEB-778146")
    assert minutes(NOW - as_utc(late.promised_at)) == 4
    # The other two are on time: promised in the future.
    assert as_utc(order(seeded, "WEB-778120").promised_at) > NOW
    assert as_utc(order(seeded, "WEB-778131").promised_at) > NOW
    assert order(seeded, "WEB-778146").late_alerted_at is None  # alert comes at 10 minutes late


def test_ready_order_has_a_ready_time_and_the_others_do_not(seeded: Session):
    assert as_utc(order(seeded, "WEB-778131").ready_at) == NOW - timedelta(minutes=2)
    assert order(seeded, "WEB-778120").ready_at is None


def test_routing_decision_is_stored_and_explains_the_choice(seeded: Session):
    row = order(seeded, "WEB-778120")
    routing = row.routing_json
    assert routing["chosen"] == "Kondapur"
    distances = [candidate["distance_km"] for candidate in routing["candidates"]]
    assert distances == sorted(distances)
    assert [c["outlet"] for c in routing["candidates"]] == ["Kondapur", "Gachibowli cloud kitchen"]
    assert row.distance_km == distances[0]


def test_order_events_tell_the_story_in_order(seeded: Session):
    def story(code: str) -> list[str]:
        rows = seeded.scalars(
            select(OrderEvent)
            .where(OrderEvent.order_id == order(seeded, code).id)
            .order_by(OrderEvent.id)
        ).all()
        return [f"{e.type}:{e.payload_json.get('to', '')}" for e in rows]

    assert story("WEB-778120") == ["order_placed:", "payment_succeeded:", "status_changed:preparing"]
    assert story("WEB-778131") == [
        "order_placed:",
        "payment_succeeded:",
        "status_changed:preparing",
        "status_changed:ready",
    ]


def test_orders_are_confirmed_by_a_recorded_message_that_is_never_sent(seeded: Session):
    messages = seeded.scalars(select(Notification)).all()
    assert len(messages) == 3
    assert all(message.channel == "whatsapp" for message in messages)
    # 15:30 UTC is 21:00 IST; the first order is promised 45 - 12 = 33 minutes later.
    first = next(m for m in messages if "WEB-778120" in m.body)
    assert "Promised by 21:33" in first.body


# ----- seed command ----------------------------------------------------------


def count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_reset_removes_everything_and_the_data_can_be_seeded_again(seeded: Session):
    reset_database(seeded)
    seeded.commit()
    assert all(count(seeded, table_class) == 0 for table_class in (Order, Outlet, User, Payment))
    assert all(
        seeded.scalar(select(func.count()).select_from(table)) == 0
        for table in Base.metadata.sorted_tables
    )
    seed_all(seeded, now=NOW, password="test-password-1")
    seeded.commit()
    assert count(seeded, Order) == 3


def test_command_seeds_an_empty_database_and_then_leaves_existing_data_alone(capsys):
    engine = make_sqlite_engine()
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    assert main([], factory) == 0
    assert "Seeded 4 outlets, 7 demo users and 3 sample orders." in capsys.readouterr().out

    with factory() as db:
        db.execute(Order.__table__.delete().where(Order.public_code == "WEB-778120"))
        db.commit()
    assert main([], factory) == 0
    assert "already contains data" in capsys.readouterr().out
    with factory() as db:
        assert count(db, Order) == 2  # untouched: the second run did not reseed

    assert main(["--reset"], factory) == 0
    with factory() as db:
        assert count(db, Order) == 3
    engine.dispose()


def test_reset_is_refused_in_production_without_force(monkeypatch, capsys):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "x" * 40)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    get_settings.cache_clear()
    engine = make_sqlite_engine()
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        assert main(["--reset"], factory) == 2
        assert "without --force" in capsys.readouterr().out
        with factory() as db:
            assert count(db, Outlet) == 0  # nothing happened
    finally:
        get_settings.cache_clear()
        engine.dispose()
