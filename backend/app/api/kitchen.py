"""The kitchen's view of one outlet. Every route checks the caller belongs to that outlet."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user, outlet_staff
from app.core.clock import as_utc, utcnow
from app.api.stream import AfterQuery, LastEventId, cursor, event_stream, sse_response
from app.core.db import get_db, get_stream_sessions
from app.models import Order, Outlet, User
from app.schemas.kitchen import AvailabilityRequest, Board, BoardLine, BoardOrder, MoveRequest, PromiseRequest
from app.services.events import events_after, latest_event_id
from app.services.access import can_access_outlet, can_override_estimate
from app.services.kitchen import (
    KitchenError,
    minutes_late,
    move_order,
    open_orders,
    outlet_dishes,
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
    # Read the cursor first: an update landing while the board loads is then replayed, never lost.
    position = latest_event_id(db, outlet_id=outlet_id)
    return Board(outlet_id=outlet_id, cursor=position, orders=[board_order(o, now) for o in open_orders(db, outlet_id)])


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


def _outlet_fetch(outlet_id: int):
    return lambda db, after: events_after(db, after, outlet_id=outlet_id)


@router.get("/events")
def poll_events(
    outlet_id: int, after: int = 0, _: User = Depends(outlet_staff), db: Session = Depends(get_db)
) -> dict:
    """Polling fallback: events after a cursor, as plain JSON."""
    events = events_after(db, max(after, 0), outlet_id=outlet_id)
    return {"events": events, "cursor": max((e["id"] for e in events), default=max(after, 0))}


@router.get("/stream")
async def stream(
    outlet_id: int,
    request: Request,
    last_event_id: LastEventId = None,
    after: AfterQuery = None,
    _: User = Depends(outlet_staff),
    open_session=Depends(get_stream_sessions),
):
    """Live events for one outlet. The caller must belong to it, checked when the stream opens."""
    with open_session() as db:
        start = cursor(last_event_id, after, lambda: latest_event_id(db, outlet_id=outlet_id))
    return sse_response(event_stream(request, open_session, _outlet_fetch(outlet_id), start))


@router.get("/items")
def list_dishes(outlet_id: int, _: User = Depends(outlet_staff), db: Session = Depends(get_db)) -> list[dict]:
    """The outlet's dishes and whether each is currently available."""
    return outlet_dishes(db, outlet_id)


mine = APIRouter(tags=["kitchen"])


@mine.get("/outlets")
def my_outlets(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[dict]:
    """Outlets the signed-in staff member can work on: their own, or every outlet for an admin."""
    rows = db.scalars(select(Outlet).order_by(Outlet.city, Outlet.name))
    allowed = [o for o in rows if can_access_outlet(user, o.id)]
    if not allowed:
        raise HTTPException(403, "You do not have access to any outlet.")
    return [{"id": o.id, "name": o.name, "city": o.city} for o in allowed]
