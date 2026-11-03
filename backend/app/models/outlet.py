from sqlalchemy import Boolean, CheckConstraint, Float, Integer, String, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import OutletKind, sql_in


class Outlet(Base):
    """A restaurant outlet or cloud kitchen that receives orders.

    Coordinates and radii are illustrative (assumption A2). The FSSAI number is
    shown to customers; the sample values are fictional (assumption A7).
    """

    __tablename__ = "outlets"
    __table_args__ = (
        CheckConstraint(sql_in("kind", OutletKind), name="kind_valid"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
        CheckConstraint("delivery_radius_km > 0", name="radius_positive"),
        CheckConstraint("length(fssai_no) = 14", name="fssai_14_characters"),
        CheckConstraint("min_prep_minutes > 0", name="min_prep_positive"),
        CheckConstraint("capacity_units_per_hour > 0", name="capacity_positive"),
        CheckConstraint("delivery_fee_paise >= 0", name="delivery_fee_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    kind: Mapped[str] = mapped_column(String(16), default=OutletKind.OUTLET.value)
    city: Mapped[str] = mapped_column(String(80))
    locality: Mapped[str] = mapped_column(String(80))
    address_line: Mapped[str] = mapped_column(String(255))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    delivery_radius_km: Mapped[float] = mapped_column(Float)
    fssai_no: Mapped[str] = mapped_column(String(14))

    # Kitchen settings used by the prep-time estimate (assumption A10).
    min_prep_minutes: Mapped[int] = mapped_column(Integer)
    capacity_units_per_hour: Mapped[int] = mapped_column(Integer)

    delivery_fee_paise: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())


class Locality(Base):
    """A named place with fixed coordinates, used by the location search (assumption A3)."""

    __tablename__ = "localities"
    __table_args__ = (
        UniqueConstraint("name", "city", name="uq_localities_name_city"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    city: Mapped[str] = mapped_column(String(80))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
