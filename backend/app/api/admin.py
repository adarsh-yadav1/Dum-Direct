"""Central menu admin: one menu for the whole chain, changed in one place. Admin role only."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_roles
from app.core.db import get_db
from app.models import Category, CityPrice, ItemVariant, MenuItem, Outlet, OutletItem
from app.models.enums import Role
from app.schemas.admin import ItemCreate, ItemPatch, ListedPatch, PricePatch, slugify

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles(Role.ADMIN))])


def _conflict(db: Session, message: str) -> HTTPException:
    db.rollback()
    return HTTPException(status.HTTP_409_CONFLICT, message)


def _item(db: Session, item_id: int) -> MenuItem:
    item = db.get(MenuItem, item_id)
    if item is None:
        raise HTTPException(404, "Dish not found.")
    return item


@router.get("/menu")
def full_menu(db: Session = Depends(get_db)) -> dict:
    outlets = list(db.scalars(select(Outlet).order_by(Outlet.city, Outlet.name)))
    listed = {(r.outlet_id, r.item_id): r.is_available for r in db.scalars(select(OutletItem))}
    prices: dict[int, dict[str, int]] = {}
    for row in db.scalars(select(CityPrice)):
        prices.setdefault(row.variant_id, {})[row.city] = row.price_paise
    categories = db.scalars(
        select(Category).options(selectinload(Category.items).selectinload(MenuItem.variants)).order_by(Category.sort_order)
    )
    return {
        "cities": sorted({o.city for o in outlets}),
        "outlets": [{"id": o.id, "name": o.name, "city": o.city} for o in outlets],
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "items": [
                    {
                        "id": i.id,
                        "name": i.name,
                        "description": i.description,
                        "image_url": i.image_url,
                        "is_veg": i.is_veg,
                        "is_active": i.is_active,
                        "base_prep_minutes": i.base_prep_minutes,
                        "variants": [
                            {"id": v.id, "label": v.label, "serves": v.serves, "price_paise": v.price_paise,
                             "city_prices": prices.get(v.id, {})}
                            for v in i.variants
                        ],
                        "outlets": [
                            {"outlet_id": o.id, "listed": (o.id, i.id) in listed, "is_available": listed.get((o.id, i.id), False)}
                            for o in outlets
                        ],
                    }
                    for i in c.items
                ],
            }
            for c in categories
        ],
    }


@router.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(body: ItemCreate, db: Session = Depends(get_db)) -> dict:
    if db.get(Category, body.category_id) is None:
        raise HTTPException(404, "Category not found.")
    item = MenuItem(
        category_id=body.category_id, slug=slugify(body.name), name=body.name, description=body.description,
        image_url=body.image_url, is_veg=body.is_veg, spice_level=body.spice_level, allergens=body.allergens,
        base_prep_minutes=body.base_prep_minutes, is_active=True,
        variants=[ItemVariant(label=v.label, serves=v.serves, price_paise=v.price_paise, sort_order=i) for i, v in enumerate(body.variants)],
    )
    db.add(item)
    try:
        db.commit()
    except IntegrityError:
        raise _conflict(db, "A dish with that name already exists.") from None
    return {"id": item.id, "name": item.name}


@router.patch("/items/{item_id}")
def edit_item(item_id: int, body: ItemPatch, db: Session = Depends(get_db)) -> dict:
    item = _item(db, item_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field in {"name", "is_active", "base_prep_minutes", "description"} and value is None:
            continue  # these cannot be cleared; image_url can
        setattr(item, field, value)
    try:
        db.commit()
    except IntegrityError:
        raise _conflict(db, "A dish with that name already exists.") from None
    return {"id": item.id, "name": item.name, "is_active": item.is_active}


@router.patch("/variants/{variant_id}")
def set_price(variant_id: int, body: PricePatch, db: Session = Depends(get_db)) -> dict:
    variant = db.get(ItemVariant, variant_id)
    if variant is None:
        raise HTTPException(404, "Portion not found.")
    variant.price_paise = body.price_paise
    db.commit()
    return {"id": variant.id, "price_paise": variant.price_paise}


def _known_city(db: Session, city: str) -> str:
    if db.scalar(select(Outlet.id).where(Outlet.city == city)) is None:
        raise HTTPException(404, "No outlet in that city.")
    return city


@router.put("/variants/{variant_id}/city-prices/{city}")
def set_city_price(variant_id: int, city: str, body: PricePatch, db: Session = Depends(get_db)) -> dict:
    if db.get(ItemVariant, variant_id) is None:
        raise HTTPException(404, "Portion not found.")
    _known_city(db, city)
    row = db.get(CityPrice, (variant_id, city))
    if row is None:
        db.add(CityPrice(variant_id=variant_id, city=city, price_paise=body.price_paise))
    else:
        row.price_paise = body.price_paise
    db.commit()
    return {"variant_id": variant_id, "city": city, "price_paise": body.price_paise}


@router.delete("/variants/{variant_id}/city-prices/{city}", status_code=status.HTTP_204_NO_CONTENT)
def clear_city_price(variant_id: int, city: str, db: Session = Depends(get_db)) -> None:
    row = db.get(CityPrice, (variant_id, city))
    if row is not None:
        db.delete(row)
        db.commit()


@router.put("/outlets/{outlet_id}/items/{item_id}")
def set_listed(outlet_id: int, item_id: int, body: ListedPatch, db: Session = Depends(get_db)) -> dict:
    if db.get(Outlet, outlet_id) is None:
        raise HTTPException(404, "Outlet not found.")
    _item(db, item_id)
    row = db.get(OutletItem, (outlet_id, item_id))
    if body.listed and row is None:
        db.add(OutletItem(outlet_id=outlet_id, item_id=item_id, is_available=True))
    elif not body.listed and row is not None:
        db.delete(row)
    db.commit()
    return {"outlet_id": outlet_id, "item_id": item_id, "listed": body.listed}

