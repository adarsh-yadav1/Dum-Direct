"""Application settings, read from environment variables.

Values come from the process environment (or a local .env file in development).
Nothing secret has a real default: production must set its own values.
"""

from functools import lru_cache
from typing import Self

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+psycopg://dumdirect:change-me@localhost:5432/dumdirect"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-to-a-long-random-string"
    cors_origins: str = "http://localhost:5173"
    cookie_secure: bool = False
    # "none" is needed when the web app and the API are on different sites; it requires
    # COOKIE_SECURE=true. "lax" suits one site and local development.
    cookie_samesite: str = "lax"
    # Password for every seeded demo account. It is a published demo credential, not a secret:
    # set DEMO_PASSWORD on a deployed instance to change it.
    demo_password: str = "dumdirect-demo-2026"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        # Hosted databases usually hand out postgres:// or postgresql:// URLs.
        # SQLAlchemy needs the driver named, so select psycopg (v3) explicitly.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @field_validator("cookie_samesite")
    @classmethod
    def _check_samesite(cls, value: str) -> str:
        value = value.lower()
        if value not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be lax, strict or none")
        return value

    @model_validator(mode="after")
    def _samesite_none_needs_secure(self) -> Self:
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
        return self

    @field_validator("env")
    @classmethod
    def _check_env(cls, value: str) -> str:
        if value not in {"development", "test", "production"}:
            raise ValueError("ENV must be development, test or production")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
