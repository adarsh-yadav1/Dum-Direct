"""Request and response shapes for the serviceability check."""

from pydantic import BaseModel, ConfigDict, Field


class ServiceabilityRequest(BaseModel):
    # Unknown fields are rejected, so a client cannot try to choose the outlet itself.
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    item_ids: list[int] = Field(default_factory=list, max_length=50)


class OutletOut(BaseModel):
    id: int
    name: str
    kind: str
    city: str
    locality: str
    address_line: str
    fssai_no: str
    delivery_radius_km: float
    delivery_fee_paise: int


class ServiceabilityResponse(BaseModel):
    serviceable: bool
    outlet: OutletOut | None = None
    distance_km: float | None = None
    eta_minutes: int | None = None
    # False when the outlet cannot supply every dish in the cart.
    cart_ok: bool = True
    unavailable_item_ids: list[int] = Field(default_factory=list)
    # Name of the nearer outlet that could not supply the cart, when the order was moved.
    rerouted_from: str | None = None
