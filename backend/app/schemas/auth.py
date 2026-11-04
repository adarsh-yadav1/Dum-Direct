"""Request and response shapes for sign-in. Unknown fields are rejected, so a client
cannot slip in a field such as `role` and have it quietly ignored or, worse, applied."""

import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(_Strict):
    name: Name
    email: EmailStr
    # Length only: no composition rules. The upper bound keeps hashing cost predictable.
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = None
    # Marketing messages need explicit opt-in (DPDP Act 2023), so the default is no.
    marketing_opt_in: bool = False

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("phone", mode="before")
    @classmethod
    def _check_phone(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("phone must be text")
        digits = value.strip()
        if digits == "":
            return None
        if not _INDIAN_MOBILE.match(digits):
            raise ValueError("phone must be a 10-digit Indian mobile number")
        return digits


class LoginRequest(_Strict):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, value: str) -> str:
        return value.lower()


class UserOut(BaseModel):
    """What the client may know about a user. Never includes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str
    outlet_id: int | None
    marketing_opt_in: bool
