"""Importing this package registers every table on Base.metadata (used by Alembic and tests)."""

from app.models.base import Base
from app.models.menu import Addon, Category, CityPrice, ItemVariant, MenuItem, OutletItem
from app.models.notification import Notification
from app.models.order import Order, OrderEvent, OrderItem, Payment
from app.models.outlet import Locality, Outlet
from app.models.user import User

__all__ = [
    "Addon",
    "Base",
    "Category",
    "CityPrice",
    "ItemVariant",
    "Locality",
    "MenuItem",
    "Notification",
    "Order",
    "OrderEvent",
    "OrderItem",
    "Outlet",
    "OutletItem",
    "Payment",
    "User",
]
