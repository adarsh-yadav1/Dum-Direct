import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Locality, MenuItem
from app.seed.catalog import seed_catalog


@pytest.fixture()
def seeded(engine):
    with Session(engine) as db:
        seed_catalog(db)
        db.commit()


def point(engine, name):
    with Session(engine) as db:
        place = db.scalars(select(Locality).where(Locality.name == name)).one()
        return {"latitude": place.latitude, "longitude": place.longitude}


def item_id(engine, name):
    with Session(engine) as db:
        return db.scalars(select(MenuItem.id).where(MenuItem.name == name)).one()


def post(client, payload):
    return client.post("/serviceability", json=payload)


@pytest.mark.parametrize(
    ("place", "outlet"),
    [
        ("Kondapur", "Kondapur"),
        ("HITEC City", "Kondapur"),
        ("Madhapur", "Kondapur"),
        ("Miyapur", "Kondapur"),
        ("Financial District", "Gachibowli cloud kitchen"),
        ("Manikonda", "Gachibowli cloud kitchen"),
        ("Kukatpally", "Kukatpally"),
        ("Indiranagar", "Indiranagar"),
    ],
)
def test_each_locality_is_served_by_the_expected_outlet(client, engine, seeded, place, outlet):
    body = post(client, point(engine, place)).json()
    assert body["serviceable"] is True
    assert body["outlet"]["name"] == outlet


@pytest.mark.parametrize(
    "place",
    ["Banjara Hills", "Jubilee Hills", "Ameerpet", "Begumpet", "Secunderabad", "LB Nagar", "Koramangala"],
)
def test_localities_outside_every_radius_are_not_serviceable(client, engine, seeded, place):
    response = post(client, point(engine, place))
    assert response.status_code == 200
    assert response.json()["serviceable"] is False
    assert response.json()["outlet"] is None


def test_response_carries_what_the_customer_needs_to_see(client, engine, seeded):
    body = post(client, point(engine, "Kondapur")).json()
    assert body["distance_km"] == 0.0
    assert body["eta_minutes"] == 20
    assert len(body["outlet"]["fssai_no"]) == 14
    assert body["cart_ok"] is True and body["rerouted_from"] is None


def test_paused_dish_reroutes_from_kondapur_to_gachibowli(client, engine, seeded):
    qubani = item_id(engine, "Qubani ka meetha")
    body = post(client, {**point(engine, "Kondapur"), "item_ids": [qubani]}).json()
    assert body["serviceable"] is True
    assert body["outlet"]["name"] == "Gachibowli cloud kitchen"
    assert body["rerouted_from"] == "Kondapur"
    assert body["cart_ok"] is True


def test_dish_nobody_covering_can_supply_is_flagged(client, engine, seeded):
    chai = item_id(engine, "Irani chai")
    # Gachibowli does not offer chai and is the only outlet covering Financial District.
    body = post(client, {**point(engine, "Financial District"), "item_ids": [chai]}).json()
    assert body["serviceable"] is True
    assert body["cart_ok"] is False
    assert body["unavailable_item_ids"] == [chai]
    assert body["outlet"]["name"] == "Gachibowli cloud kitchen"


def test_client_cannot_choose_the_outlet(client, engine, seeded):
    for field in ("outlet_id", "outlet", "outlet_name"):
        response = post(client, {**point(engine, "Kondapur"), field: 3})
        assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"latitude": 91, "longitude": 78},
        {"latitude": -91, "longitude": 78},
        {"latitude": 17, "longitude": 181},
        {"latitude": "north", "longitude": 78},
        {"longitude": 78},
        {"latitude": 17, "longitude": 78, "item_ids": list(range(51))},
        {"latitude": 17, "longitude": 78, "item_ids": ["a"]},
    ],
)
def test_invalid_input_is_rejected(client, seeded, payload):
    assert post(client, payload).status_code == 422


def test_check_is_public_and_stores_nothing(client, engine, seeded):
    from app.models import Order

    assert post(client, point(engine, "Kondapur")).status_code == 200
    with Session(engine) as db:
        assert db.scalars(select(Order)).first() is None
