"""Signed session tokens.

A session is a short-lived JWT (HS256) held in an httpOnly cookie. It carries only
the user id and its times. The user's role and outlet are read from the database
on every request, so a changed role or a removed account takes effect immediately
and cannot be kept alive by an old token.
"""

from datetime import datetime, timedelta

import jwt

from app.core.clock import utcnow
from app.core.config import get_settings

SESSION_COOKIE_NAME = "dd_session"
# Long enough for a kitchen shift, short enough that a lost tablet is not a standing risk.
SESSION_LIFETIME = timedelta(hours=12)

_ALGORITHM = "HS256"


class InvalidToken(Exception):
    """The token is missing, malformed, expired or not signed by this server."""


def create_session_token(
    user_id: int, *, now: datetime | None = None, lifetime: timedelta = SESSION_LIFETIME
) -> str:
    issued = now or utcnow()
    payload = {"sub": str(user_id), "iat": issued, "exp": issued + lifetime}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=_ALGORITHM)


def read_session_token(token: str) -> int:
    """Return the user id, or raise InvalidToken.

    The accepted algorithm is fixed, so a token that names another one (including
    "none") is rejected instead of being trusted.
    """
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[_ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
        return int(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as error:
        raise InvalidToken from error
