"""A mock payment gateway that behaves like a real one (assumption A8).

The amount is always the order total held by the server, never a figure from the client. The
caller picks only the method and, because this is a mock, the outcome it wants simulated. A
settled payment is final: paying again cannot charge twice, and a failed payment means a new order.
"""

import secrets
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.models import Order, OrderEvent, Payment
from app.models.enums import OrderStatus, PaymentStatus
from app.services.order_state import check_transition


@dataclass
class PaymentError(Exception):
    status_code: int
    code: str
    message: str


def _gateway(outcome: str) -> tuple[str, str]:
    """The mock gateway's answer: a status and a provider reference."""
    status = PaymentStatus.SUCCEEDED if outcome == "success" else PaymentStatus.FAILED
    return status.value, f"mock_{secrets.token_hex(12)}"


def pay_order(db: Session, order_code: str, user_id: int, method: str, outcome: str) -> Order:
    order = db.scalar(
        select(Order).where(Order.public_code == order_code, Order.user_id == user_id).with_for_update()
    )
    if order is None:
        raise PaymentError(404, "order_not_found", "Order not found.")

    if order.status != OrderStatus.PENDING_PAYMENT.value:
        settled = [p for p in order.payments if p.status == PaymentStatus.SUCCEEDED.value]
        if settled:  # a double click or retry after success: same answer, no second charge
            return order
        raise PaymentError(409, "payment_closed", "This order can no longer be paid. Please place a new order.")

    status, reference = _gateway(outcome)
    db.add(
        Payment(
            order_id=order.id,
            method=method,
            status=status,
            provider_ref=reference,
            amount_paise=order.total_paise,
        )
    )
    target = OrderStatus.NEW if status == PaymentStatus.SUCCEEDED.value else OrderStatus.PAYMENT_FAILED
    check_transition(order.status, target.value)
    order.status = target.value
    db.add(
        OrderEvent(
            order_id=order.id,
            outlet_id=order.outlet_id,
            type="payment_succeeded" if target is OrderStatus.NEW else "payment_failed",
            payload_json={"method": method, "amount_paise": order.total_paise},
            actor_user_id=user_id,
        )
    )
    if target is OrderStatus.NEW:
        db.add(
            OrderEvent(
                order_id=order.id,
                outlet_id=order.outlet_id,
                type="order_new",
                payload_json={"public_code": order.public_code},
            )
        )
    db.commit()
    return order
