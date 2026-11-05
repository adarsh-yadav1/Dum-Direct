"""Request and response shapes for orders. Requests carry no prices, totals or outlet:
the server works all of those out, and unknown fields are rejected."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.schemas.serviceability import OutletOut

Text = Annotated[str, StringConstraints(strip_whitespace=True)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrderLineIn(_Strict):
    variant_id: int
    qty: int = Field(ge=1, le=20)
    addon_ids: list[int] = Field(default_factory=list, max_length=10)
    notes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] | None = None

    @field_validator("addon_ids")
    @classmethod
    def _no_repeated_addon(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("an add-on can be chosen once per line")
        return value

    @field_validator("notes")
    @classmethod
    def _blank_notes_are_none(cls, value: str | None) -> str | None:
        return value or None


class OrderCreate(_Strict):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address_line: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=200)]
    landmark: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    lines: list[OrderLineIn] = Field(min_length=1, max_length=30)


class PayRequest(_Strict):
    method: Literal["upi", "card"]
    # The gateway is a mock: the caller says which result to simulate.
    outcome: Literal["success", "failure"] = "success"


class OrderLineOut(BaseModel):
    name: str
    variant_label: str
    qty: int
    unit_price_paise: int
    line_total_paise: int
    addons: list[dict]
    notes: str | None


class PaymentOut(BaseModel):
    method: str
    status: str
    amount_paise: int


class OrderOut(BaseModel):
    public_code: str
    status: str
    outlet: OutletOut
    distance_km: float | None
    rerouted_from: str | None
    lines: list[OrderLineOut]
    subtotal_paise: int
    delivery_fee_paise: int
    total_paise: int
    gst_included_paise: int
    placed_at: datetime
    promised_at: datetime | None
    payment: PaymentOut | None
    # Pass to the order's stream as ?after= to receive every update after this view.
    last_event_id: int
