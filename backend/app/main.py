"""DumDirect API entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.menu import router as menu_router
from app.api.orders import router as orders_router
from app.api.serviceability import router as serviceability_router
from app.core.config import get_settings
from app.core.origin import OriginCheck

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
# Added after CORS, so it runs first and a refused write never reaches a route.
app.add_middleware(OriginCheck)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness check used by Docker, the host and the tests."""
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(serviceability_router)
app.include_router(menu_router)
app.include_router(orders_router)
