from datetime import time

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    CityPrice,
    ItemVariant,
    Locality,
    MenuItem,
    Outlet,
    OutletItem,
)
from app.seed.catalog import city_price_paise, seed_catalog, slugify
from app.seed.catalog_data import ALLERGEN_VOCABULARY, BASE_CITY
from app.services.geo import haversine_km


@pytest.fixture()
def seeded(session: Session) -> Session:
    seed_catalog(session)
    session.commit()
    return session


def covering_outlets(db: Session, locality_name: str) -> list[str]:
    """Outlets whose delivery radius covers a locality, nearest first."""
    place = db.scalars(select(Locality).where(Locality.name == locality_name)).one()
    hits = []
    for outlet in db.scalars(select(Outlet)):
        distance = haversine_km(
            place.latitude, place.longitude, outlet.latitude, outlet.longitude
        )
        if distance <= outlet.delivery_radius_km:
            hits.append((distance, outlet.name))
    return [name for _, name in sorted(hits)]


def price_of(db: Session, item_name: str, label: str) -> int:
    return db.scalars(
        select(ItemVariant.price_paise)
        .join(MenuItem)
        .where(MenuItem.name == item_name, ItemVariant.label == label)
    ).one()


def test_slugify():
    assert slugify("Chicken 65") == "chicken-65"
    assert slugify("Mirchi ka salan") == "mirchi-ka-salan"


def test_expected_amount_of_demo_data(seeded: Session):
    count = lambda model: len(seeded.scalars(select(model)).all())  # noqa: E731
    assert count(Outlet) == 4
    assert count(Locality) == 16
    assert count(Category) == 6
    assert count(MenuItem) == 18  # a short, scannable menu


def test_every_item_has_a_portion_and_only_known_allergens(seeded: Session):
    for item in seeded.scalars(select(MenuItem)):
        assert item.variants, f"{item.name} has no portion to price"
        assert set(item.allergens) <= ALLERGEN_VOCABULARY, item.name
        assert 0 <= item.spice_level <= 3


def test_prices_reconcile_with_the_three_sample_orders(seeded: Session):
    # WEB-778120: family pack x1 + Double ka meetha x2 = Rs 1,180
    assert price_of(seeded, "Chicken dum biryani", "Family pack") + 2 * price_of(
        seeded, "Double ka meetha", "Regular"
    ) == 118_000
    # WEB-778131: Veg biryani x2 + Mirchi ka salan x1 = Rs 640
    assert 2 * price_of(seeded, "Veg biryani", "Regular") + price_of(
        seeded, "Mirchi ka salan", "Regular"
    ) == 64_000
    # WEB-778146: Mutton haleem x3 = Rs 1,050
    assert 3 * price_of(seeded, "Mutton haleem", "Regular") == 105_000


def test_haleem_is_a_time_based_category(seeded: Session):
    haleem = seeded.scalars(select(Category).where(Category.name == "Haleem")).one()
    assert (haleem.available_from, haleem.available_to) == (time(16, 0), time(23, 30))
    biryani = seeded.scalars(select(Category).where(Category.name == "Biryani")).one()
    assert biryani.available_from is None and biryani.available_to is None


@pytest.mark.parametrize(
    ("locality", "expected"),
    [
        ("Kukatpally", ["Kukatpally"]),
        ("HITEC City", ["Kondapur", "Gachibowli cloud kitchen"]),  # nearest wins
        ("Madhapur", ["Kondapur", "Gachibowli cloud kitchen", "Kukatpally"]),
        ("Miyapur", ["Kondapur"]),
        ("Manikonda", ["Gachibowli cloud kitchen"]),  # inside its radius, near the edge
        ("Indiranagar", ["Indiranagar"]),
        ("Secunderabad", []),  # not serviceable
        ("Jubilee Hills", []),
    ],
)
def test_coverage_examples_for_the_routing_demo(seeded: Session, locality: str, expected: list[str]):
    assert covering_outlets(seeded, locality) == expected


def test_other_cities_get_a_price_for_every_portion_and_the_base_city_none(seeded: Session):
    variants = seeded.scalars(select(ItemVariant)).all()
    overrides = {
        (row.variant_id, row.city): row.price_paise for row in seeded.scalars(select(CityPrice))
    }
    assert {city for _, city in overrides} == {"Bengaluru"}
    assert BASE_CITY not in {city for _, city in overrides}
    for variant in variants:
        price = overrides[(variant.id, "Bengaluru")]
        assert price >= variant.price_paise
        assert price % 500 == 0  # whole multiples of Rs 5


def test_city_price_rounds_half_up_to_five_rupees():
    assert city_price_paise(99_000, 110) == 109_000  # Rs 990 -> 1,089 -> Rs 1,090
    assert city_price_paise(32_000, 110) == 35_000  # Rs 320 -> 352 -> Rs 350
    assert city_price_paise(4_000, 110) == 4_500  # Rs 40 -> 44 -> Rs 45


def test_one_outlet_has_an_item_paused_that_another_still_offers(seeded: Session):
    def row(outlet: str, item: str) -> OutletItem | None:
        return seeded.scalars(
            select(OutletItem)
            .join(Outlet, Outlet.id == OutletItem.outlet_id)
            .join(MenuItem, MenuItem.id == OutletItem.item_id)
            .where(Outlet.name == outlet, MenuItem.name == item)
        ).one_or_none()

    assert row("Kondapur", "Qubani ka meetha").is_available is False
    assert row("Gachibowli cloud kitchen", "Qubani ka meetha").is_available is True
    assert row("Gachibowli cloud kitchen", "Irani chai") is None  # not offered at all
    assert row("Kondapur", "Irani chai").is_available is True
