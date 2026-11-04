import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql://u:p@host/db?sslmode=require", "postgresql+psycopg://u:p@host/db?sslmode=require"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("sqlite://", "sqlite://"),
    ],
)
def test_database_url_selects_the_psycopg_driver(given: str, expected: str):
    assert Settings(database_url=given).database_url == expected


def test_samesite_none_is_refused_without_secure_cookies():
    with pytest.raises(ValueError, match="requires COOKIE_SECURE"):
        Settings(cookie_samesite="none", cookie_secure=False)
    assert Settings(cookie_samesite="none", cookie_secure=True).cookie_samesite == "none"


def test_samesite_value_is_checked_and_case_insensitive():
    assert Settings(cookie_samesite="Strict").cookie_samesite == "strict"
    with pytest.raises(ValueError, match="lax, strict or none"):
        Settings(cookie_samesite="sometimes")
