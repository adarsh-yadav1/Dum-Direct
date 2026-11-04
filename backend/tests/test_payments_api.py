import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderEvent, Payment, User
from app.core.security import hash_password
from tests.test_orders_api import body, login, noon, place, seeded, variant  # noqa: F401


@pytest.fixture()
def order(client, engine, seeded, noon):  # noqa: F811
    login(client)
    v = variant(engine, "Veg biryani")
    return place(client, body(engine, [{"variant_id": v.id, "qty": 2}])).json()


def pay(client, code, **payload):
    return client.post(f"/orders/{code}/pay", json={"method": "upi", **payload})


def test_successful_payment_moves_the_order_to_new(client, engine, order):
    response = pay(client, order["public_code"])
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "new"
    assert data["payment"] == {"method": "upi", "status": "succeeded", "amount_paise": order["total_paise"]}
    with Session(engine) as db:
        assert [e.type for e in db.scalars(select(OrderEvent).order_by(OrderEvent.id))] == [
            "order_created", "payment_succeeded", "order_new"]


def test_failed_payment_is_final(client, engine, order):
    data = pay(client, order["public_code"], outcome="failure").json()
    assert data["status"] == "payment_failed" and data["payment"]["status"] == "failed"
    again = pay(client, order["public_code"])
    assert again.status_code == 409 and again.json()["detail"]["code"] == "payment_closed"
    with Session(engine) as db:
        assert len(db.scalars(select(Payment)).all()) == 1


def test_paying_twice_does_not_charge_twice(client, engine, order):
    pay(client, order["public_code"])
    second = pay(client, order["public_code"])
    assert second.status_code == 200 and second.json()["status"] == "new"
    with Session(engine) as db:
        assert len(db.scalars(select(Payment)).all()) == 1


def test_amount_always_comes_from_the_server(client, engine, order):
    assert pay(client, order["public_code"], amount_paise=1).status_code == 422
    pay(client, order["public_code"])
    with Session(engine) as db:
        assert db.scalars(select(Payment)).one().amount_paise == db.scalars(select(Order)).one().total_paise


@pytest.mark.parametrize("payload", [{"method": "cash"}, {"method": "upi", "outcome": "maybe"}, {}])
def test_invalid_payment_requests_are_rejected(client, order, payload):
    assert client.post(f"/orders/{order['public_code']}/pay", json=payload).status_code == 422


def test_only_the_owner_can_pay(client, engine, order):
    with Session(engine) as db:
        db.add(User(email="other@example.com", name="O", role="customer", password_hash=hash_password("password123")))
        db.commit()
    client.post("/auth/logout")
    login(client, "other@example.com")
    assert pay(client, order["public_code"]).status_code == 404


def test_payment_needs_sign_in(client, order):
    client.post("/auth/logout")
    assert pay(client, order["public_code"]).status_code == 401
