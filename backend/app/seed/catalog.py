"""Loads the sample catalogue into the database."""

import re

from sqlalchemy.orm import Session

from app.models import (
    Addon,
    Category,
    CityPrice,
    ItemVariant,
    Locality,
    MenuItem,
    Outlet,
    OutletItem,
)
from app.seed.images import IMAGE_URLS
from app.seed.catalog_data import (
    CATEGORIES,
    CITY_PRICE_PERCENT,
    ITEMS,
    LOCALITIES,
    NOT_OFFERED,
    OUTLETS,
    PAUSED,
)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def city_price_paise(base_paise: int, percent: int) -> int:
    """Base price scaled by a percentage and rounded half up to the nearest Rs 5 (500 paise)."""
    return (base_paise * percent + 25_000) // 50_000 * 500


def seed_catalog(db: Session) -> None:
    """Insert outlets, localities, categories, items, portions, add-ons, availability and city prices."""
    outlets = [Outlet(**spec) for spec in OUTLETS]
    db.add_all(outlets)
    db.add_all(
        Locality(name=name, city=city, latitude=lat, longitude=lng)
        for name, city, lat, lng in LOCALITIES
    )

    categories = {
        name: Category(name=name, sort_order=order, available_from=start, available_to=end)
        for name, order, start, end in CATEGORIES
    }
    db.add_all(categories.values())

    items: list[MenuItem] = []
    for position, spec in enumerate(ITEMS, start=1):
        item = MenuItem(
            category=categories[spec.category],
            slug=slugify(spec.name),
            name=spec.name,
            description=spec.description,
            image_url=IMAGE_URLS.get(spec.name),  # linked, not stored: see seed/images.py
            is_veg=spec.is_veg,
            spice_level=spec.spice_level,
            allergens=list(spec.allergens),
            base_prep_minutes=spec.prep_minutes,
            sort_order=position,
        )
        item.variants = [
            ItemVariant(label=label, price_paise=rupees * 100, serves=serves, sort_order=index)
            for index, (label, rupees, serves) in enumerate(spec.variants)
        ]
        item.addons = [Addon(name=name, price_paise=rupees * 100) for name, rupees in spec.addons]
        items.append(item)
    db.add_all(items)
    db.flush()  # assigns the ids the availability and price rows refer to

    for outlet in outlets:
        for item in items:
            key = (outlet.name, item.name)
            if key in NOT_OFFERED:
                continue
            db.add(
                OutletItem(outlet_id=outlet.id, item_id=item.id, is_available=key not in PAUSED)
            )

    for city, percent in CITY_PRICE_PERCENT.items():
        for item in items:
            for variant in item.variants:
                db.add(
                    CityPrice(
                        variant_id=variant.id,
                        city=city,
                        price_paise=city_price_paise(variant.price_paise, percent),
                    )
                )
    db.flush()
