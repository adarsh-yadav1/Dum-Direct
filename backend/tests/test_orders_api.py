import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import Addon, ItemVariant, Locality, MenuItem, Order, OrderEvent, User
from app.seed.catalog import seed_catalog
from tests.test_menu import ist

KEY = "key-0000-0001"


@pytest.fixture()
def seeded(engine):
    with Session(engine) as db:
        seed_catalog(db)
        db.add(User(email="cust@example.com", name="Cust", role="customer", password_hash=hash_password("password123")))
        db.add(User(email="chef@example.com", name="Chef", role="kitchen", outlet_id=1, password_hash=hash_password("password123")))
        db.commit()


@pytest.fixture()
def noon(monkeypatch):
    monkeypatch.setattr("app.api.orders.utcnow", lambda: ist(12))


def login(client, email="cust@example.com"):
    assert client.post("/auth/login", json={"email": email, "password": "password123"}).status_code == 200


def where(engine, name):
    with Session(engine) as db:
        p = db.scalars(select(Locality).where(Locality.name == name)).one()
        return {"latitude": p.latitude, "longitude": p.longitude}


def variant(engine, item, label="Regular"):
    with Session(engine) as db:
        return db.scalars(select(ItemVariant).join(MenuItem).where(MenuItem.name == item, ItemVariant.label == label)).one()


def body(engine, lines, place="Kondapur", **extra):
    return {**where(engine, place), "address_line": "12 Test Street", "lines": lines, **extra}


def place(client, payload, key=KEY):
    return client.post("/orders", json=payload, headers={"Idempotency-Key": key})


def test_order_is_priced_and_routed_by_the_server(client, engine, seeded, noon):
    login(client)
    v = variant(engine, "Chicken dum biryani", "Family pack")
    response = place(client, body(engine, [{"variant_id": v.id, "qty": 2}]))
    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "pending_payment"
    assert order["outlet"]["name"] == "Kondapur"
    assert order["subtotal_paise"] == v.price_paise * 2
    assert order["total_paise"] == order["subtotal_paise"] + order["delivery_fee_paise"]
    assert order["promised_at"] is None and order["payment"] is None
    assert order["public_code"].startswith("WEB-")


def test_addons_are_priced_from_the_database(client, engine, seeded, noon):
    login(client)
    with Session(engine) as db:
        addon = db.scalars(select(Addon)).first()
        v = db.scalars(select(ItemVariant).where(ItemVariant.item_id == addon.item_id)).first()
        addon_price, variant_price, addon_id, variant_id = addon.price_paise, v.price_paise, addon.id, v.id
    order = place(client, body(engine, [{"variant_id": variant_id, "qty": 1, "addon_ids": [addon_id]}])).json()
    assert order["lines"][0]["unit_price_paise"] == variant_price + addon_price


def test_client_supplied_prices_totals_and_outlet_are_refused(client, engine, seeded, noon):
    login(client)
    v = variant(engine, "Veg biryani")
    for extra in ({"outlet_id": 3}, {"total_paise": 1}, {"delivery_fee_paise": 0}):
        assert place(client, body(engine, [{"variant_id": v.id, "qty": 1}], **extra)).status_code == 422
    assert place(client, body(engine, [{"variant_id": v.id, "qty": 1, "price_paise": 1}])).status_code == 422


def test_bengaluru_order_uses_city_prices(client, engine, seeded, noon):
    login(client)
    v = variant(engine, "Veg biryani")
    order = place(client, body(engine, [{"variant_id": v.id, "qty": 1}], place="Indiranagar")).json()
    assert order["outlet"]["name"] == "Indiranagar"
    assert order["subtotal_paise"] == (v.price_paise * 110 + 25_000) // 50_000 * 500


def test_same_key_returns_the_same_order(client, engine, seeded, noon):
    login(client)
    payload = body(engine, [{"variant_id": variant(engine, "Veg biryani").id, "qty": 1}])
    first, second = place(client, payload), place(client, payload)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["public_code"] == second.json()["public_code"]
    with Session(engine) as db:
        assert len(db.scalars(select(Order)).all()) == 1


def test_different_key_makes_a_second_order(client, engine, seeded, noon):
    login(client)
    payload = body(engine, [{"variant_id": variant(engine, "Veg biryani").id, "qty": 1}])
    assert place(client, payload, "key-0000-0001").json()["public_code"] != place(client, payload, "key-0000-0002").json()["public_code"]


@pytest.mark.parametrize("key", ["short", "has space here", "x" * 81, "bad/chars!!"])
def test_bad_idempotency_keys_are_rejected(client, engine, seeded, noon, key):
    login(client)
    payload = body(engine, [{"variant_id": variant(engine, "Veg biryani").id, "qty": 1}])
    assert place(client, payload, key).status_code == 422


def test_missing_idempotency_key_is_rejected(client, engine, seeded, noon):
    login(client)
    payload = body(engine, [{"variant_id": variant(engine, "Veg biryani").id, "qty": 1}])
    assert client.post("/orders", json=payload).status_code == 422


def test_sign_in_and_role_are_required(client, engine, seeded, noon):
    payload = body(engine, [{"variant_id": variant(engine, "Veg biryani").id, "qty": 1}])
    assert place(client, payload).status_code == 401
    login(client, "chef@example.com")
    assert place(client, payload).status_code == 403


def test_unserviceable_address_is_refused(client, engine, seeded, noon):
    login(client)
    payload = body(engine, [{"variant_id": variant(engine, "Veg biryani").id, "qty": 1}], place="Banjara Hills")
    response = place(client, payload)
    assert response.status_code == 422 and response.json()["detail"]["code"] == "not_serviceable"


def test_paused_dish_is_rerouted_to_an_outlet_that_has_it(client, engine, seeded, noon):
    login(client)
    v = variant(engine, "Qubani ka meetha")
    order = place(client, body(engine, [{"variant_id": v.id, "qty": 1}])).json()
    assert order["outlet"]["name"] == "Gachibowli cloud kitchen"
    assert order["rerouted_from"] == "Kondapur"


def test_dish_nobody_can_supply_is_a_conflict_naming_the_dish(client, engine, seeded, noon):
    login(client)
    v = variant(engine, "Irani chai", "Cup")
    response = place(client, body(engine, [{"variant_id": v.id, "qty": 1}], place="Financial District"))
    assert response.status_code == 409
    assert response.json()["detail"] == {"code": "items_unavailable", "message": response.json()["detail"]["message"], "item_ids": [v.item_id]}


def test_haleem_is_refused_at_noon(client, engine, seeded, noon):
    login(client)
    v = variant(engine, "Mutton haleem")
    response = place(client, body(engine, [{"variant_id": v.id, "qty": 1}]))
    assert response.status_code == 409 and response.json()["detail"]["code"] == "not_orderable_now"


def test_haleem_is_accepted_in_the_evening(client, engine, seeded, monkeypatch):
    monkeypatch.setattr("app.api.orders.utcnow", lambda: ist(19))
    login(client)
    v = variant(engine, "Mutton haleem")
    assert place(client, body(engine, [{"variant_id": v.id, "qty": 1}])).status_code == 201


def test_unknown_dish_and_foreign_addon_are_refused(client, engine, seeded, noon):
    login(client)
    assert place(client, body(engine, [{"variant_id": 99999, "qty": 1}])).json()["detail"]["code"] == "unknown_dish"
    with Session(engine) as db:
        addon = db.scalars(select(Addon)).first()
        other = db.scalars(select(ItemVariant).where(ItemVariant.item_id != addon.item_id)).first()
        addon_id, variant_id = addon.id, other.id
    response = place(client, body(engine, [{"variant_id": variant_id, "qty": 1, "addon_ids": [addon_id]}]))
    assert response.json()["detail"]["code"] == "invalid_addon"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(lines=[]),
        lambda p: p["lines"][0].update(qty=0),
        lambda p: p["lines"][0].update(qty=21),
        lambda p: p["lines"][0].update(addon_ids=[1, 1]),
        lambda p: p["lines"][0].update(notes="x" * 201),
        lambda p: p.update(address_line="no"),
        lambda p: p.update(latitude=100),
        lambda p: p.update(lines=p["lines"] * 31),
    ],
)
def test_invalid_orders_are_rejected(client, engine, seeded, noon, mutate):
    login(client)
    payload = body(engine, [{"variant_id": variant(engine, "Veg biryani").id, "qty": 1}])
    mutate(payload)
    assert place(client, payload).status_code == 422


def test_creation_is_logged_and_nothing_partial_is_left_on_failure(client, engine, seeded, noon):
    login(client)
    place(client, body(engine, [{"variant_id": variant(engine, "Veg biryani").id, "qty": 1}]))
    place(client, body(engine, [{"variant_id": 99999, "qty": 1}]), "key-0000-0002")
    with Session(engine) as db:
        assert [e.type for e in db.scalars(select(OrderEvent))] == ["order_created"]
        assert len(db.scalars(select(Order)).all()) == 1


def test_customers_see_only_their_own_orders(client, engine, seeded, noon):
    login(client)
    code = place(client, body(engine, [{"variant_id": variant(engine, "Veg biryani").id, "qty": 1}])).json()["public_code"]
    assert client.get(f"/orders/{code}").status_code == 200
    with Session(engine) as db:
        db.add(User(email="other@example.com", name="Other", role="customer", password_hash=hash_password("password123")))
        db.commit()
    client.post("/auth/logout")
    login(client, "other@example.com")
    assert client.get(f"/orders/{code}").status_code == 404
    assert client.get("/orders/WEB-000000").status_code == 404
