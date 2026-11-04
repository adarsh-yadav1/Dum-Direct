from datetime import UTC, datetime, time

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, MenuItem, OutletItem
from app.seed.catalog import seed_catalog
from app.services.menu import build_menu, effective_price_paise, in_window
from tests.factories import make_item, make_outlet


def ist(hour, minute=0):
    """A UTC instant that is hour:minute in IST (IST is UTC+05:30)."""
    total = hour * 60 + minute - 330
    day = 5 + (total // 1440)  # a fixed November date; the day itself does not matter
    total %= 1440
    return datetime(2026, 11, day, total // 60, total % 60, tzinfo=UTC)


def window(start, end):
    return Category(name="Window", available_from=start, available_to=end)


def test_no_window_is_always_orderable():
    assert in_window(window(None, None), ist(3, 0))


def test_window_start_is_inclusive_and_end_is_exclusive():
    haleem = window(time(16, 0), time(23, 30))
    assert not in_window(haleem, ist(15, 59))
    assert in_window(haleem, ist(16, 0))
    assert in_window(haleem, ist(23, 29))
    assert not in_window(haleem, ist(23, 30))


def test_window_uses_ist_not_utc():
    # 11:30 UTC is 17:00 IST, inside the window; 16:00 UTC is 21:30 IST, also inside.
    haleem = window(time(16, 0), time(23, 30))
    assert in_window(haleem, datetime(2026, 11, 5, 11, 30, tzinfo=UTC))
    assert not in_window(haleem, datetime(2026, 11, 5, 8, 0, tzinfo=UTC))  # 13:30 IST


def test_city_price_overrides_the_base_price():
    assert effective_price_paise(30000, 7, {7: 33000}) == 33000
    assert effective_price_paise(30000, 8, {7: 33000}) == 30000


def test_unlisted_paused_and_inactive_items(session):
    outlet = make_outlet(session)
    listed, paused, unlisted, inactive = (make_item(session, n).item_id for n in ["L", "P", "U", "I"])
    session.add_all(
        [
            OutletItem(outlet_id=outlet.id, item_id=listed),
            OutletItem(outlet_id=outlet.id, item_id=paused, is_available=False),
            OutletItem(outlet_id=outlet.id, item_id=inactive),
        ]
    )
    session.get(MenuItem, inactive).is_active = False
    session.flush()
    items = {i["id"]: i for c in build_menu(session, outlet, ist(12))["categories"] for i in c["items"]}
    assert set(items) == {listed, paused}
    assert items[listed]["orderable"] and not items[listed]["sold_out"]
    assert items[paused]["sold_out"] and not items[paused]["orderable"]


def test_item_outside_its_category_window_is_shown_but_not_orderable(session):
    outlet = make_outlet(session)
    item = make_item(session, "Evening dish").item_id
    session.add(OutletItem(outlet_id=outlet.id, item_id=item))
    category = session.get(MenuItem, item).category
    category.available_from, category.available_to = time(16, 0), time(23, 30)
    session.flush()
    morning = build_menu(session, outlet, ist(10))["categories"][0]
    evening = build_menu(session, outlet, ist(18))["categories"][0]
    assert morning["orderable_now"] is False and morning["items"][0]["orderable"] is False
    assert morning["available_from"] == "16:00"
    assert evening["orderable_now"] is True and evening["items"][0]["orderable"] is True


# --- the API against the seeded catalogue ---------------------------------------------------


@pytest.fixture()
def seeded(engine):
    with Session(engine) as db:
        seed_catalog(db)
        db.commit()


def locate(engine, name):
    from app.models import Locality

    with Session(engine) as db:
        place = db.scalars(select(Locality).where(Locality.name == name)).one()
        return {"latitude": place.latitude, "longitude": place.longitude}


def menu(client, engine, place, monkeypatch, now=None):
    monkeypatch.setattr("app.api.menu.utcnow", lambda: now or ist(12))
    return client.get("/menu", params=locate(engine, place)).json()


def flat(body):
    return {i["name"]: i for c in body["categories"] for i in c["items"]}


def test_menu_comes_from_the_assigned_outlet(client, engine, seeded, monkeypatch):
    body = menu(client, engine, "Madhapur", monkeypatch)
    assert body["serviceable"] and body["outlet"]["name"] == "Kondapur"
    assert body["gst_note"] == "All prices include 5% GST."
    assert len(body["outlet"]["fssai_no"]) == 14


def test_unserviceable_point_has_no_menu(client, engine, seeded, monkeypatch):
    body = menu(client, engine, "Banjara Hills", monkeypatch)
    assert body == {**body, "serviceable": False, "outlet": None, "categories": []}


def test_qubani_is_sold_out_at_kondapur(client, engine, seeded, monkeypatch):
    item = flat(menu(client, engine, "Kondapur", monkeypatch))["Qubani ka meetha"]
    assert item["sold_out"] and not item["orderable"]


def test_chai_is_not_listed_at_gachibowli(client, engine, seeded, monkeypatch):
    assert "Irani chai" not in flat(menu(client, engine, "Financial District", monkeypatch))
    assert "Irani chai" in flat(menu(client, engine, "Kondapur", monkeypatch))


def test_haleem_is_orderable_only_in_the_evening(client, engine, seeded, monkeypatch):
    noon = menu(client, engine, "Kondapur", monkeypatch, ist(12))
    evening = menu(client, engine, "Kondapur", monkeypatch, ist(19))
    assert flat(noon)["Mutton haleem"]["orderable"] is False
    assert flat(evening)["Mutton haleem"]["orderable"] is True
    haleem = next(c for c in evening["categories"] if c["name"] == "Haleem")
    assert (haleem["available_from"], haleem["available_to"]) == ("16:00", "23:30")


def test_bengaluru_prices_are_ten_percent_higher_than_hyderabad(client, engine, seeded, monkeypatch):
    hyd = flat(menu(client, engine, "Kondapur", monkeypatch))
    blr = flat(menu(client, engine, "Indiranagar", monkeypatch))
    name = "Mutton haleem"
    for h, b in zip(hyd[name]["variants"], blr[name]["variants"], strict=True):
        assert b["price_paise"] == (h["price_paise"] * 110 + 25_000) // 50_000 * 500


def test_items_carry_veg_mark_allergens_and_portions(client, engine, seeded, monkeypatch):
    body = flat(menu(client, engine, "Kondapur", monkeypatch))
    chai = body["Irani chai"]
    assert chai["is_veg"] is True and chai["allergens"] == ["milk"]
    assert all(v["price_paise"] > 0 and v["serves"] >= 1 for i in body.values() for v in i["variants"])


@pytest.mark.parametrize("params", [{}, {"latitude": 95, "longitude": 78}, {"latitude": 17, "longitude": "x"}])
def test_invalid_location_is_rejected(client, seeded, params):
    assert client.get("/menu", params=params).status_code == 422


def test_the_menu_cannot_be_asked_for_by_outlet(client, engine, seeded, monkeypatch):
    # An outlet parameter is ignored: the answer still follows the location.
    monkeypatch.setattr("app.api.menu.utcnow", lambda: ist(12))
    body = client.get("/menu", params={**locate(engine, "Kukatpally"), "outlet_id": 1}).json()
    assert body["outlet"]["name"] == "Kukatpally"
