"""Shared FastAPI dependencies: who is calling, and are they allowed."""

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.db import get_db, get_stream_sessions
from app.core.tokens import SESSION_COOKIE_NAME, InvalidToken, read_session_token
from app.models import User
from app.models.enums import Role
from app.services.access import can_access_outlet


def _read_user(request: Request, db: Session) -> User | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        user_id = read_session_token(token)
    except InvalidToken:
        return None
    return db.get(User, user_id)


def current_user_optional(request: Request, db: Session = Depends(get_db)) -> User | None:
    """The signed-in user, or None. A bad, expired or orphaned token counts as signed out."""
    return _read_user(request, db)


def current_user(user: User | None = Depends(current_user_optional)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in required.")
    return user


def require_roles(*roles: Role):
    """Dependency factory: allow only the listed roles."""
    allowed = {role.value for role in roles}

    def dependency(user: User = Depends(current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this.")
        return user

    return dependency


def outlet_staff(outlet_id: int, user: User = Depends(current_user)) -> User:
    """Kitchen or manager of this outlet, or an admin. `outlet_id` is the route's path parameter."""
    if not can_access_outlet(user, outlet_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this outlet.")
    return user


def stream_user(request: Request, open_session=Depends(get_stream_sessions)) -> User:
    """Who is opening a live stream.

    A normal request keeps one database session until its response is finished. A stream lasts
    minutes, so that would hold a connection per open screen and exhaust the pool. Here the
    session is borrowed for the lookup and returned at once; the user is detached from it.
    """
    with open_session() as db:
        user = _read_user(request, db)
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in required.")
        db.expunge(user)
    return user


def stream_outlet_staff(outlet_id: int, user: User = Depends(stream_user)) -> User:
    if not can_access_outlet(user, outlet_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this outlet.")
    return user


def stream_customer(user: User = Depends(stream_user)) -> User:
    if user.role != Role.CUSTOMER.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not have access to this.")
    return user
