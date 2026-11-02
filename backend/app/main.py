"""DumDirect API entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

settings = get_settings()

# Fail fast: a production deployment must never run with the placeholder secret.
if settings.is_production and settings.jwt_secret.startswith("change-me"):
    raise RuntimeError("JWT_SECRET must be set to a real secret in production")

app = FastAPI(
    title="DumDirect API",
    version="0.1.0",
    description="Direct ordering, outlet routing and kitchen display for a Hyderabadi restaurant chain.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Idempotency-Key", "Last-Event-ID"],
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness check used by Docker, the host and the tests."""
    return {"status": "ok"}
