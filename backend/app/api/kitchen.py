"""The kitchen's view of one outlet. Every route checks the caller belongs to that outlet."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import current_user, outlet_staff
from app.core.clock import as_utc, utcnow
from app.core.db import get_db
from app.models import Order, User
from app.schemas.kitchen import AvailabilityRequest, Board, BoardLine, BoardOrder, MoveRequest, PromiseRequest
from app.services.access import can_override_estimate
from app.services.kitchen import (
    KitchenError,
    minutes_late,
    move_order,
    open_orders,
    outlet_order,
    override_promise,
    set_availability,
    sweep_late_orders,
)

router = APIRouter(prefix="/outlets/{outlet_id}", tags=["kitchen"])


def _fail(error: KitchenError) -> HTTPException:
    return HTTPException(error.status_code, {"code": error.code, "message": error.message})


def board_order(order: Order, now) -> BoardOrder:
    return BoardOrder(
        public_code=order.public_code,
        status=order.status,
        placed_at=as_utc(order.placed_at),
        promised_at=as_utc(order.promised_at) if order.promised_at else None,
        minutes_late=minutes_late(order, now),
        late_alerted=order.late_alerted_at is not None,
        overridden=order.override_min is not None,
        lines=[
            BoardLine(
                name=i.name_snapshot,
                variant_label=i.variant_label_snapshot,
                qty=i.qty,
                addons=[a["name"] for a in (i.addons_json or [])],
                notes=i.notes,
            )
            for i in order.items
        ],
    )


@router.get("/orders", response_model=Board)
def get_board(outlet_id: int, _: User = Depends(outlet_staff), db: Session = Depends(get_db)) -> Board:
    now = utcnow()
    sweep_late_orders(db, now)
    return Board(outlet_id=outlet_id, orders=[board_order(o, now) for o in open_orders(db, outlet_id)])


@router.post("/orders/{code}/status", response_model=BoardOrder)
def change_status(
    outlet_id: int, code: str, body: MoveRequest, user: User = Depends(outlet_staff), db: Session = Depends(get_db)
) -> BoardOrder:
    try:
        now = utcnow()
        return board_order(move_order(db, outlet_order(db, outlet_id, code), body.status, user.id, now), now)
    except KitchenError as error:
        raise _fail(error) from None


@router.post("/orders/{code}/promise", response_model=BoardOrder)
def change_promise(
    outlet_id: int, code: str, body: PromiseRequest, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> BoardOrder:
    """Only the outlet's manager (or an admin) may change a promise; kitchen staff may not."""
    if not can_override_estimate(user, outlet_id):
        raise HTTPException(403, "Only the outlet manager can change a promised time.")
    try:
        now = utcnow()
        return board_order(override_promise(db, outlet_order(db, outlet_id, code), body.minutes, user.id, now), now)
    except KitchenError as error:
        raise _fail(error) from None


@router.put("/items/{item_id}/availability")
def change_availability(
    outlet_id: int, item_id: int, body: AvailabilityRequest, user: User = Depends(outlet_staff), db: Session = Depends(get_db)
) -> dict:
    try:
        row = set_availability(db, outlet_id, item_id, body.is_available, user.id)
    except KitchenError as error:
        raise _fail(error) from None
    return {"item_id": row.item_id, "is_available": row.is_available}
