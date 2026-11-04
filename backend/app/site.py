"""One origin for everything: the API under /api and the web app at /.

Serving both from one address keeps the sign-in cookie first-party. Browsers that block
third-party cookies by default (Safari, iPhone) would drop it if the web app and the API
lived on different sites. It also removes the need for CORS in production.

Run this module's `site` in production (`uvicorn app.site:site`). `app.main:app` stays the
plain API, which is what the tests use.
"""

from pathlib import Path

from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.main import app as api

_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


class SecurityHeaders:
    """Add standard hardening headers to every response, streaming ones included."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _SECURITY_HEADERS.items():
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)


class SinglePageAppFiles(StaticFiles):
    """Serve the built web app. Unknown paths without a file extension are client-side
    routes (for example /orders/12), so they get index.html; a missing file such as
    /assets/old.js stays a 404 instead of being answered with HTML."""

    async def get_response(self, path: str, scope: Scope):
        try:
            response = await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or "." in Path(path).name:
                raise
            path = "index.html"
            response = await super().get_response(path, scope)
        # Built assets have hashed names and never change; the page itself must stay fresh.
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable" if path.startswith("assets/") else "no-cache"
        )
        return response


def create_site(static_dir: str) -> Starlette:
    routes = [Mount("/api", app=api)]
    if static_dir and (Path(static_dir) / "index.html").is_file():
        routes.append(Mount("/", app=SinglePageAppFiles(directory=static_dir, html=True)))
    return Starlette(routes=routes, middleware=[Middleware(SecurityHeaders)])


site = create_site(get_settings().static_dir)
