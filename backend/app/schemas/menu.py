"""Response shapes for the public menu."""

from pydantic import BaseModel

from app.schemas.serviceability import OutletOut


class VariantOut(BaseModel):
    id: int
    label: str
    serves: int
    price_paise: int


class AddonOut(BaseModel):
    id: int
    name: str
    price_paise: int


class ItemOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    image_url: str | None
    is_veg: bool
    spice_level: int
    allergens: list[str]
    sold_out: bool
    orderable: bool
    variants: list[VariantOut]
    addons: list[AddonOut]


class CategoryOut(BaseModel):
    id: int
    name: str
    available_from: str | None
    available_to: str | None
    orderable_now: bool
    items: list[ItemOut]


class MenuResponse(BaseModel):
    serviceable: bool
    outlet: OutletOut | None = None
    distance_km: float | None = None
    gst_note: str | None = None
    categories: list[CategoryOut] = []
