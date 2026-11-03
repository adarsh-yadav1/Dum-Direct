"""Application settings, read from environment variables.

Values come from the process environment (or a local .env file in development).
Nothing secret has a real default: production must set its own values.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+psycopg://dumdirect:change-me@localhost:5432/dumdirect"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-to-a-long-random-string"
    cors_origins: str = "http://localhost:5173"
    cookie_secure: bool = False

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

    @field_validator("env")
    @classmethod
    def _check_env(cls, value: str) -> str:
        if value not in {"development", "test", "production"}:
            raise ValueError("ENV must be development, test or production")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
