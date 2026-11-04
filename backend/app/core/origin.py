"""Defence against cross-site request forgery for cookie sessions.

Browsers attach an Origin header to every write they send, including writes from the
site's own pages. A write is allowed when its Origin is on the configured list or is
the host the request was addressed to (the web app served by this same server). A write
that names any other site is refused before it reaches a route.

Requests with no Origin (curl, server-to-server) are not a browser acting for another
site, so they pass; they still need a valid session to do anything.

This is plain ASGI middleware, not BaseHTTPMiddleware, so it never interferes with
streaming responses such as the live order updates.
"""

from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import get_settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def is_allowed_origin(origin: str, host: str, allowed: list[str]) -> bool:
    if origin in allowed:
        return True
    own = urlsplit(origin).netloc.lower()
    # "null" and malformed origins have no host, so they never match.
    return bool(own) and own == host.lower()


class OriginCheck:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in SAFE_METHODS:
            headers = Headers(scope=scope)
            origin = headers.get("origin")
            if origin and not is_allowed_origin(
                origin, headers.get("host", ""), get_settings().cors_origin_list
            ):
                response = JSONResponse({"detail": "Origin not allowed."}, status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)
