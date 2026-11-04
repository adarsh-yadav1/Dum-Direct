"""Which outlet will serve a delivery point. Public: nothing is stored."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.schemas.serviceability import OutletOut, ServiceabilityRequest, ServiceabilityResponse
from app.services.routing import NOT_SERVICEABLE, SERVICEABLE, assign_outlet, provisional_eta_minutes

router = APIRouter(tags=["serviceability"])


@router.post("/serviceability", response_model=ServiceabilityResponse)
def check_serviceability(
    body: ServiceabilityRequest, db: Session = Depends(get_db)
) -> ServiceabilityResponse:
    """Pick the outlet for a point and cart. An address nobody delivers to is a normal answer (200)."""
    decision = assign_outlet(db, body.latitude, body.longitude, body.item_ids)
    if decision.status == NOT_SERVICEABLE or decision.chosen is None:
        return ServiceabilityResponse(serviceable=False)

    outlet = decision.chosen.outlet
    distance = decision.chosen.distance_km
    return ServiceabilityResponse(
        serviceable=True,
        outlet=OutletOut.model_validate(outlet, from_attributes=True),
        distance_km=round(distance, 2),
        eta_minutes=provisional_eta_minutes(outlet, distance, get_settings().delivery_minutes_per_km),
        cart_ok=decision.status == SERVICEABLE,
        unavailable_item_ids=decision.unavailable_item_ids,
        rerouted_from=decision.rerouted_from.name if decision.rerouted_from else None,
    )
