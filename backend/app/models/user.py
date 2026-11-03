from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, created_at_column
from app.models.enums import Role, sql_in


class User(Base):
    """A customer, an outlet's kitchen or manager account, or a central admin.

    Kitchen and manager accounts belong to exactly one outlet; customers and
    admins belong to none (assumption A12). Only name, email and an optional
    phone are collected, to keep personal data to the minimum (DPDP Act 2023).
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(sql_in("role", Role), name="role_valid"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint(
            "(role IN ('kitchen', 'manager') AND outlet_id IS NOT NULL)"
            " OR (role IN ('customer', 'admin') AND outlet_id IS NULL)",
            name="role_matches_outlet",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(16), default=Role.CUSTOMER.value)
    outlet_id: Mapped[int | None] = mapped_column(ForeignKey("outlets.id", ondelete="RESTRICT"))

    # Marketing messages need explicit opt-in, recorded with the time it was given.
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    marketing_opt_in_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    created_at: Mapped[datetime] = created_at_column()
