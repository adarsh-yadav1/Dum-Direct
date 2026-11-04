"""DumDirect API entry point."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
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


_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def reject_foreign_origins(request: Request, call_next):
    """Defend cookie sessions against cross-site request forgery.

    Browsers attach an Origin header to every cross-site write. If one names a site that is
    not on the allowed list, the request is refused before it reaches any route. Requests with
    no Origin (curl, server-to-server, same-site form posts) are not browsers acting for
    another site, so they pass; they still need a valid session to do anything.
    """
    origin = request.headers.get("origin")
    if (
        request.method not in _SAFE_METHODS
        and origin
        and origin not in get_settings().cors_origin_list
    ):
        return JSONResponse({"detail": "Origin not allowed."}, status_code=403)
    return await call_next(request)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Liveness check used by Docker, the host and the tests."""
    return {"status": "ok"}

app.include_router(auth_router)
