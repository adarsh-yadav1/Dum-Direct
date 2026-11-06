"""Shapes for the central menu admin. Unknown fields are rejected; prices are integer paise."""

import re
from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.seed.images import ALLOWED_IMAGE_HOSTS

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
Price = Annotated[int, Field(ge=100, le=1_000_000)]  # ₹1 to ₹10,000


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_image(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    parts = urlparse(value)
    if len(value) > 255 or parts.scheme != "https" or parts.hostname not in ALLOWED_IMAGE_HOSTS:
        raise ValueError("image must be an https link on " + ", ".join(sorted(ALLOWED_IMAGE_HOSTS)))
    return value


class ItemPatch(_Strict):
    name: Name | None = None
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None
    is_active: bool | None = None
    image_url: str | None = None
    base_prep_minutes: Annotated[int, Field(ge=1, le=180)] | None = None

    @field_validator("image_url")
    @classmethod
    def _image(cls, value: str | None) -> str | None:
        return _check_image(value)


class VariantIn(_Strict):
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    serves: int = Field(ge=1, le=20)
    price_paise: Price


class ItemCreate(_Strict):
    category_id: int
    name: Name
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    is_veg: bool
    spice_level: int = Field(ge=0, le=3, default=1)
    allergens: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]] = Field(default_factory=list, max_length=10)
    base_prep_minutes: int = Field(ge=1, le=180)
    image_url: str | None = None
    variants: list[VariantIn] = Field(min_length=1, max_length=6)

    @field_validator("image_url")
    @classmethod
    def _image(cls, value: str | None) -> str | None:
        return _check_image(value)

    @field_validator("variants")
    @classmethod
    def _distinct_labels(cls, value: list[VariantIn]) -> list[VariantIn]:
        labels = [v.label.lower() for v in value]
        if len(set(labels)) != len(labels):
            raise ValueError("portion names must be different")
        return value


class PricePatch(_Strict):
    price_paise: Price


class ListedPatch(_Strict):
    listed: bool


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "item"
