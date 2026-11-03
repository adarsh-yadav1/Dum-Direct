"""Shared SQLAlchemy base, naming convention and portable column types.

Conventions used by every model:
- Money is stored as integer paise, never as floating point.
- Timestamps are timezone-aware and stored in UTC; the UI converts to IST.
- Enumerations are plain strings guarded by CHECK constraints, not native
  database enums, so adding a value is a simple migration.
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column

# Stable constraint names keep Alembic migrations predictable and reviewable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# BIGINT on PostgreSQL, plain INTEGER on SQLite (which only auto-increments INTEGER keys).
BigIntPK = BigInteger().with_variant(Integer(), "sqlite")

# Binary JSON (JSONB) on PostgreSQL, ordinary JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")

UTCDateTime = DateTime(timezone=True)


def created_at_column() -> MappedColumn[datetime]:
    return mapped_column(UTCDateTime, server_default=func.now(), nullable=False)


def updated_at_column() -> MappedColumn[datetime]:
    return mapped_column(
        UTCDateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


__all__ = [
    "Base",
    "BigIntPK",
    "JSONType",
    "Mapped",
    "UTCDateTime",
    "created_at_column",
    "updated_at_column",
]
