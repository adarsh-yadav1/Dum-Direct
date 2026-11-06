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


def _production(**over):
    from app.core.config import Settings

    base = {"env": "production", "jwt_secret": "x" * 40, "cookie_secure": True}
    return Settings(_env_file=None, **{**base, **over})


def test_production_accepts_a_strong_secret_and_secure_cookies():
    assert _production().is_production


def test_production_refuses_the_default_or_a_short_secret():
    import pytest

    for secret in ["change-me-to-a-long-random-string", "short", "x" * 31]:
        with pytest.raises(ValueError, match="JWT_SECRET"):
            _production(jwt_secret=secret)


def test_production_requires_secure_cookies():
    import pytest

    with pytest.raises(ValueError, match="COOKIE_SECURE"):
        _production(cookie_secure=False)


def test_development_keeps_its_easy_defaults():
    from app.core.config import Settings

    assert Settings(_env_file=None, env="development").jwt_secret.startswith("change-me")
