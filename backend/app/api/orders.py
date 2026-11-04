"""Placing and viewing orders. Customers only; each sees only their own."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.clock import utcnow
from app.core.db import get_db
from app.models import Order, Outlet, User
from app.models.enums import Role
from app.schemas.orders import OrderCreate, OrderLineOut, OrderOut, PaymentOut
from app.schemas.serviceability import OutletOut
from app.services.orders import OrderError, create_order

router = APIRouter(prefix="/orders", tags=["orders"])

IdempotencyKey = Annotated[
    str, Header(alias="Idempotency-Key", min_length=8, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
]


def present(db: Session, order: Order) -> OrderOut:
    routing = order.routing_json or {}
    payment = order.payments[-1] if order.payments else None
    return OrderOut(
        public_code=order.public_code,
        status=order.status,
        outlet=OutletOut.model_validate(db.get(Outlet, order.outlet_id), from_attributes=True),
        distance_km=order.distance_km,
        rerouted_from=routing.get("rerouted_from"),
        lines=[
            OrderLineOut(
                name=i.name_snapshot,
                variant_label=i.variant_label_snapshot,
                qty=i.qty,
                unit_price_paise=i.unit_price_paise,
                line_total_paise=i.unit_price_paise * i.qty,
                addons=i.addons_json or [],
                notes=i.notes,
            )
            for i in order.items
        ],
        subtotal_paise=order.subtotal_paise,
        delivery_fee_paise=order.delivery_fee_paise,
        total_paise=order.total_paise,
        gst_included_paise=order.gst_included_paise,
        placed_at=order.placed_at,
        promised_at=order.promised_at,
        payment=PaymentOut(method=payment.method, status=payment.status, amount_paise=payment.amount_paise)
        if payment
        else None,
    )


def own_order(db: Session, user: User, code: str) -> Order:
    """The customer's own order. Anyone else's is reported as missing, not forbidden."""
    order = db.scalar(select(Order).where(Order.public_code == code, Order.user_id == user.id))
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found.")
    return order


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def place_order(
    body: OrderCreate,
    response: Response,
    idempotency_key: IdempotencyKey,
    user: User = Depends(require_roles(Role.CUSTOMER)),
    db: Session = Depends(get_db),
) -> OrderOut:
    try:
        order, created = create_order(db, user, body, idempotency_key, utcnow())
    except OrderError as error:
        raise HTTPException(error.status_code, error.detail()) from None
    if not created:
        response.status_code = status.HTTP_200_OK
    return present(db, order)


@router.get("/{code}", response_model=OrderOut)
def view_order(
    code: str, user: User = Depends(require_roles(Role.CUSTOMER)), db: Session = Depends(get_db)
) -> OrderOut:
    return present(db, own_order(db, user, code))
