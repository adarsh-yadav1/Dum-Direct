"""Shapes for the kitchen board and its actions. Unknown fields are rejected."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MoveRequest(_Strict):
    status: Literal["preparing", "ready", "handed_off", "completed", "cancelled"]


class PromiseRequest(_Strict):
    minutes: int = Field(ge=1, le=240)


class AvailabilityRequest(_Strict):
    is_available: bool


class BoardLine(BaseModel):
    name: str
    variant_label: str
    qty: int
    addons: list[str]
    notes: str | None


class BoardOrder(BaseModel):
    public_code: str
    status: str
    placed_at: datetime
    promised_at: datetime | None
    minutes_late: int
    late_alerted: bool
    overridden: bool
    lines: list[BoardLine]


class Board(BaseModel):
    outlet_id: int
    # Pass to the stream as ?after= so no update between loading the board and connecting is missed.
    cursor: int
    orders: list[BoardOrder]
