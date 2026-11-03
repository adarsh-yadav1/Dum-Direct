from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_column
from app.models.enums import NotificationChannel, sql_in


class Notification(Base):
    """A WhatsApp or SMS message. Messages are only recorded, never sent (assumption A9)."""

    __tablename__ = "notifications"
    __table_args__ = (CheckConstraint(sql_in("channel", NotificationChannel), name="channel_valid"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(String(10))
    template: Mapped[str] = mapped_column(String(60))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
