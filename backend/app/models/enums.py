"""String enumerations shared by models, services and API schemas."""

from enum import StrEnum


class Role(StrEnum):
    CUSTOMER = "customer"
    KITCHEN = "kitchen"
    MANAGER = "manager"
    ADMIN = "admin"


# Roles that belong to exactly one outlet (assumption A12).
OUTLET_BOUND_ROLES = (Role.KITCHEN, Role.MANAGER)


class OutletKind(StrEnum):
    OUTLET = "outlet"
    CLOUD_KITCHEN = "cloud_kitchen"


class OrderStatus(StrEnum):
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_FAILED = "payment_failed"
    NEW = "new"
    PREPARING = "preparing"
    READY = "ready"  # ready for pickup by the delivery partner's rider
    HANDED_OFF = "handed_off"  # rider has collected it
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentMethod(StrEnum):
    UPI = "upi"
    CARD = "card"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NotificationChannel(StrEnum):
    WHATSAPP = "whatsapp"
    SMS = "sms"


def sql_in(column: str, enum_cls: type[StrEnum]) -> str:
    """Build the text of a CHECK constraint, for example: role IN ('customer', 'admin')."""
    values = ", ".join(f"'{member.value}'" for member in enum_cls)
    return f"{column} IN ({values})"
