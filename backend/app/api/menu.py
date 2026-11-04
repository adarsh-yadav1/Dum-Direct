"""The menu for a delivery point. The outlet is chosen by the system, never by the caller."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.core.db import get_db
from app.schemas.menu import MenuResponse
from app.schemas.serviceability import OutletOut
from app.services.menu import build_menu
from app.services.routing import NOT_SERVICEABLE, assign_outlet

router = APIRouter(tags=["menu"])


@router.get("/menu", response_model=MenuResponse)
def get_menu(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    db: Session = Depends(get_db),
) -> MenuResponse:
    """Menu of the outlet that serves this point, with that outlet's availability and city prices."""
    decision = assign_outlet(db, latitude, longitude, [])
    if decision.status == NOT_SERVICEABLE or decision.chosen is None:
        return MenuResponse(serviceable=False)

    outlet = decision.chosen.outlet
    return MenuResponse(
        serviceable=True,
        outlet=OutletOut.model_validate(outlet, from_attributes=True),
        distance_km=round(decision.chosen.distance_km, 2),
        **build_menu(db, outlet, utcnow()),
    )
