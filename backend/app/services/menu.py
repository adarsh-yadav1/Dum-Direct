"""What an outlet's menu looks like right now, and what each portion costs there.

Visibility rules:
- A dish the outlet does not list is left out. A listed but paused dish is shown as sold out.
- Inactive dishes are left out everywhere.
- A category with a daily window is always shown, but it can be ordered from only inside the
  window (wall-clock IST, start inclusive, end exclusive), so "Haleem from 4 pm" is visible all day.
- A portion costs the city price when the outlet's city has one, otherwise its own price.
"""

from datetime import datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.clock import IST, as_utc
from app.models import Category, CityPrice, MenuItem, Outlet, OutletItem
from app.services.pricing import GST_PERCENT


def local_time(now: datetime) -> time:
    return as_utc(now).astimezone(IST).time().replace(tzinfo=None)


def in_window(category: Category, now: datetime) -> bool:
    """True when the category can be ordered from at `now`. No window means always."""
    if category.available_from is None or category.available_to is None:
        return True
    return category.available_from <= local_time(now) < category.available_to


def city_prices(db: Session, city: str) -> dict[int, int]:
    """Variant id to its price override in this city."""
    rows = db.execute(select(CityPrice.variant_id, CityPrice.price_paise).where(CityPrice.city == city))
    return {variant_id: price for variant_id, price in rows}


def effective_price_paise(base_paise: int, variant_id: int, overrides: dict[int, int]) -> int:
    return overrides.get(variant_id, base_paise)


def build_menu(db: Session, outlet: Outlet, now: datetime) -> dict:
    offered = {
        row.item_id: row.is_available
        for row in db.scalars(select(OutletItem).where(OutletItem.outlet_id == outlet.id))
    }
    overrides = city_prices(db, outlet.city)
    categories = db.scalars(
        select(Category)
        .options(
            selectinload(Category.items).selectinload(MenuItem.variants),
            selectinload(Category.items).selectinload(MenuItem.addons),
        )
        .order_by(Category.sort_order, Category.id)
    )

    sections = []
    for category in categories:
        orderable_now = in_window(category, now)
        items = []
        for item in category.items:
            if not item.is_active or item.id not in offered:
                continue
            items.append(
                {
                    "id": item.id,
                    "slug": item.slug,
                    "name": item.name,
                    "description": item.description,
                    "image_url": item.image_url,
                    "is_veg": item.is_veg,
                    "spice_level": item.spice_level,
                    "allergens": list(item.allergens or []),
                    "sold_out": not offered[item.id],
                    "orderable": offered[item.id] and orderable_now,
                    "variants": [
                        {
                            "id": v.id,
                            "label": v.label,
                            "serves": v.serves,
                            "price_paise": effective_price_paise(v.price_paise, v.id, overrides),
                        }
                        for v in item.variants
                    ],
                    "addons": [
                        {"id": a.id, "name": a.name, "price_paise": a.price_paise}
                        for a in item.addons
                        if a.is_active
                    ],
                }
            )
        if items:
            sections.append(
                {
                    "id": category.id,
                    "name": category.name,
                    "available_from": category.available_from.strftime("%H:%M") if category.available_from else None,
                    "available_to": category.available_to.strftime("%H:%M") if category.available_to else None,
                    "orderable_now": orderable_now,
                    "items": items,
                }
            )
    return {
        "gst_note": f"All prices include {GST_PERCENT}% GST.",
        "categories": sections,
    }
