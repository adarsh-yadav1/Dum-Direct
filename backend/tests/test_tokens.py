from datetime import timedelta

import jwt
import pytest

from app.core.clock import utcnow
from app.core.config import get_settings
from app.core.tokens import InvalidToken, create_session_token, read_session_token


def test_a_token_returns_the_user_it_was_made_for():
    assert read_session_token(create_session_token(42)) == 42


def test_an_expired_token_is_rejected():
    token = create_session_token(42, lifetime=timedelta(seconds=-1))
    with pytest.raises(InvalidToken):
        read_session_token(token)


def test_a_tampered_token_is_rejected():
    header, payload, signature = create_session_token(42).split(".")
    flipped = ("A" if signature[0] != "A" else "B") + signature[1:]
    with pytest.raises(InvalidToken):
        read_session_token(f"{header}.{payload}.{flipped}")


def test_a_token_signed_with_another_secret_is_rejected():
    now = utcnow()
    forged = jwt.encode(
        {"sub": "1", "iat": now, "exp": now + timedelta(hours=1)},
        "some-other-secret-that-is-long-enough-123",
        algorithm="HS256",
    )
    with pytest.raises(InvalidToken):
        read_session_token(forged)


def test_a_token_that_asks_for_no_signature_is_rejected():
    now = utcnow()
    unsigned = jwt.encode({"sub": "1", "iat": now, "exp": now + timedelta(hours=1)}, None, algorithm="none")
    with pytest.raises(InvalidToken):
        read_session_token(unsigned)


def test_a_token_without_a_subject_is_rejected():
    now = utcnow()
    token = jwt.encode(
        {"iat": now, "exp": now + timedelta(hours=1)}, get_settings().jwt_secret, algorithm="HS256"
    )
    with pytest.raises(InvalidToken):
        read_session_token(token)


@pytest.mark.parametrize("garbage", ["", "abc", "a.b.c", "Bearer xyz"])
def test_garbage_is_rejected(garbage: str):
    with pytest.raises(InvalidToken):
        read_session_token(garbage)
