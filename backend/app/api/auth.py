"""Registration, sign-in, sign-out and the current user."""

from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.db import get_db
from app.core.rate_limit import Throttle, get_login_throttle
from app.core.security import hash_password, needs_rehash, verify_password
from app.core.tokens import SESSION_COOKIE_NAME, SESSION_LIFETIME, create_session_token
from app.models import User
from app.models.enums import Role
from app.schemas.auth import LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

_DUPLICATE = "An account with this email already exists."
_BAD_LOGIN = "Invalid email or password."
_TOO_MANY = "Too many failed sign-in attempts. Try again later."


@lru_cache
def _dummy_hash() -> str:
    """Verified against when the email is unknown, so timing does not reveal which emails exist."""
    return hash_password("not-a-real-password")


def _cookie_options() -> dict:
    settings = get_settings()
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }


def _start_session(response: Response, user: User) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(user.id),
        max_age=int(SESSION_LIFETIME.total_seconds()),
        **_cookie_options(),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> User:
    """Create a customer account. Staff and admin accounts are never created here."""
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE)

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
        phone=body.phone,
        role=Role.CUSTOMER.value,
        marketing_opt_in=body.marketing_opt_in,
        marketing_opt_in_at=utcnow() if body.marketing_opt_in else None,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two requests with the same email raced
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, _DUPLICATE) from None

    _start_session(response, user)
    return user


@router.post("/login", response_model=UserOut)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    throttle: Throttle = Depends(get_login_throttle),
) -> User:
    key = f"{request.client.host if request.client else 'unknown'}|{body.email}"
    wait = throttle.retry_after(key)
    if wait:  # checked first, so a blocked client costs no password hashing
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, _TOO_MANY, headers={"Retry-After": str(wait)}
        )

    user = db.scalar(select(User).where(User.email == body.email))
    password_ok = verify_password(body.password, user.password_hash if user else _dummy_hash())
    if user is None or not password_ok:
        throttle.record_failure(key)
        # One message for both cases: the response must not reveal which emails have accounts.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, _BAD_LOGIN)
    throttle.reset(key)

    if needs_rehash(user.password_hash):  # upgrade old hashes quietly after a correct password
        user.password_hash = hash_password(body.password)
        db.commit()

    _start_session(response, user)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(SESSION_COOKIE_NAME, **_cookie_options())
    return response


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)) -> User:
    return user
