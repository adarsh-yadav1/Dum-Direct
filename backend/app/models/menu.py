from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, updated_at_column


class Category(Base):
    """A menu section. An optional daily window gives time-based menus.

    The window is wall-clock time in the outlets' local zone (IST) and must not
    cross midnight; an overnight section would be modelled as two categories.
    """

    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(
            "(available_from IS NULL AND available_to IS NULL)"
            " OR (available_from IS NOT NULL AND available_to IS NOT NULL"
            " AND available_from < available_to)",
            name="window_complete_and_ordered",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    available_from: Mapped[time | None] = mapped_column(Time)
    available_to: Mapped[time | None] = mapped_column(Time)

    items: Mapped[list["MenuItem"]] = relationship(
        back_populates="category", order_by="MenuItem.sort_order"
    )


class MenuItem(Base):
    """A dish. Its price lives on its variants (portions), never on the item itself."""

    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("spice_level BETWEEN 0 AND 3", name="spice_level_range"),
        CheckConstraint("base_prep_minutes > 0", name="base_prep_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(String(255))
    is_veg: Mapped[bool] = mapped_column(Boolean)
    spice_level: Mapped[int] = mapped_column(Integer, default=0)
    # Allergen names such as "milk", "gluten", "peanut", stored as a JSON list.
    allergens: Mapped[list[str]] = mapped_column(JSONType, default=list)
    base_prep_minutes: Mapped[int] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    category: Mapped[Category] = relationship(back_populates="items")
    variants: Mapped[list["ItemVariant"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="ItemVariant.sort_order"
    )
    addons: Mapped[list["Addon"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", order_by="Addon.id"
    )


class ItemVariant(Base):
    """A portion of an item, such as Regular, Large or Family pack. Prices include 5% GST."""

    __tablename__ = "item_variants"
    __table_args__ = (
        UniqueConstraint("item_id", "label", name="uq_item_variants_item_label"),
        CheckConstraint("price_paise > 0", name="price_positive"),
        CheckConstraint("serves >= 1", name="serves_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(60))
    price_paise: Mapped[int] = mapped_column(Integer)
    serves: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    item: Mapped[MenuItem] = relationship(back_populates="variants")


class Addon(Base):
    __tablename__ = "addons"
    __table_args__ = (
        UniqueConstraint("item_id", "name", name="uq_addons_item_name"),
        CheckConstraint("price_paise >= 0", name="price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    price_paise: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())

    item: Mapped[MenuItem] = relationship(back_populates="addons")


class CityPrice(Base):
    """Overrides a variant's price in one city. No row means the variant's own price applies."""

    __tablename__ = "city_prices"
    __table_args__ = (CheckConstraint("price_paise > 0", name="price_positive"),)

    variant_id: Mapped[int] = mapped_column(
        ForeignKey("item_variants.id", ondelete="CASCADE"), primary_key=True
    )
    city: Mapped[str] = mapped_column(String(80), primary_key=True)
    price_paise: Mapped[int] = mapped_column(Integer)


class OutletItem(Base):
    """Whether an outlet offers an item right now.

    A missing row means the outlet does not offer the item at all. A row with
    is_available false means it is paused (out of stock) at that outlet.
    """

    __tablename__ = "outlet_items"

    outlet_id: Mapped[int] = mapped_column(
        ForeignKey("outlets.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="CASCADE"), primary_key=True
    )
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = updated_at_column()
