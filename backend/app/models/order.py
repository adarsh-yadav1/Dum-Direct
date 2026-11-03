from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    BigIntPK,
    JSONType,
    UTCDateTime,
    created_at_column,
    updated_at_column,
)
from app.models.enums import OrderStatus, PaymentMethod, PaymentStatus, sql_in


class Order(Base):
    """A customer order, assigned to one outlet by the routing service.

    Amounts are integer paise and include 5% GST; gst_included_paise is the GST
    contained in the total, shown on the bill. The outlet is never supplied by
    the client: it is stored together with the routing decision that chose it.
    """

    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(sql_in("status", OrderStatus), name="status_valid"),
        CheckConstraint(
            "total_paise = subtotal_paise - discount_paise + delivery_fee_paise",
            name="total_matches_components",
        ),
        CheckConstraint("discount_paise <= subtotal_paise", name="discount_within_subtotal"),
        CheckConstraint(
            "subtotal_paise >= 0 AND discount_paise >= 0"
            " AND delivery_fee_paise >= 0 AND gst_included_paise >= 0",
            name="amounts_non_negative",
        ),
        CheckConstraint("override_min IS NULL OR override_min > 0", name="override_positive"),
        # A repeated submit by the same customer returns the same order.
        UniqueConstraint("user_id", "idempotency_key", name="uq_orders_user_idempotency_key"),
        # The kitchen board query: open orders for one outlet, oldest first.
        Index("ix_orders_outlet_status_placed", "outlet_id", "status", "placed_at"),
        Index("ix_orders_user_placed", "user_id", "placed_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    public_code: Mapped[str] = mapped_column(String(20), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.PENDING_PAYMENT.value)

    delivery_latitude: Mapped[float] = mapped_column(Float)
    delivery_longitude: Mapped[float] = mapped_column(Float)
    address_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    distance_km: Mapped[float | None] = mapped_column(Float)
    # Candidate outlets, distances and the reason one was chosen, so routing can be explained.
    routing_json: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    subtotal_paise: Mapped[int] = mapped_column(Integer)
    discount_paise: Mapped[int] = mapped_column(Integer, default=0)
    delivery_fee_paise: Mapped[int] = mapped_column(Integer, default=0)
    total_paise: Mapped[int] = mapped_column(Integer)
    gst_included_paise: Mapped[int] = mapped_column(Integer)

    placed_at: Mapped[datetime] = mapped_column(UTCDateTime)
    promised_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    preparing_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    ready_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    ai_estimate_min: Mapped[int | None] = mapped_column(Integer)
    override_min: Mapped[int | None] = mapped_column(Integer)
    override_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    late_alerted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    idempotency_key: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime] = updated_at_column()

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id"
    )
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="Payment.id"
    )


class OrderItem(Base):
    """One line of an order. Names and prices are snapshots, so later menu edits never alter history."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="qty_positive"),
        CheckConstraint("unit_price_paise >= 0", name="unit_price_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id", ondelete="RESTRICT"))
    variant_id: Mapped[int] = mapped_column(ForeignKey("item_variants.id", ondelete="RESTRICT"))
    name_snapshot: Mapped[str] = mapped_column(String(120))
    variant_label_snapshot: Mapped[str] = mapped_column(String(60))
    unit_price_paise: Mapped[int] = mapped_column(Integer)
    qty: Mapped[int] = mapped_column(Integer)
    addons_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    notes: Mapped[str | None] = mapped_column(String(200))

    order: Mapped[Order] = relationship(back_populates="items")


class Payment(Base):
    """A payment attempt. The gateway is a mock that behaves like a real one (assumption A8)."""

    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint(sql_in("method", PaymentMethod), name="method_valid"),
        CheckConstraint(sql_in("status", PaymentStatus), name="status_valid"),
        CheckConstraint("amount_paise > 0", name="amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    method: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(12), default=PaymentStatus.PENDING.value)
    provider_ref: Mapped[str | None] = mapped_column(String(64), unique=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = updated_at_column()

    order: Mapped[Order] = relationship(back_populates="payments")


class OrderEvent(Base):
    """Append-only log of everything that happens to an order.

    It is the audit trail and the source of the real-time stream: its
    increasing id lets a reconnecting client resume exactly where it stopped.
    outlet_id is repeated here so one outlet's stream is a single indexed query.
    """

    __tablename__ = "order_events"
    __table_args__ = (
        Index("ix_order_events_outlet_id_id", "outlet_id", "id"),
        Index("ix_order_events_order_id_id", "order_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id", ondelete="RESTRICT"))
    type: Mapped[str] = mapped_column(String(40))
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = created_at_column()
