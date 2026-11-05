"""Server-Sent Events plumbing shared by the kitchen and customer streams.

A stream replays events after a cursor, then polls the log about once a second. Each poll
opens and closes its own short database session, so an open stream never holds a connection.
Streams end after a fixed time; the browser reconnects by itself and sends Last-Event-ID, so
nothing is lost, permission is re-checked every few minutes and long-lived connections do
not pile up behind proxies.
"""

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from typing import Annotated

from fastapi import Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.events import PAGE_SIZE, format_sse

SessionOpener = Callable[[], Session]
Fetch = Callable[[Session, int], list[dict]]

LastEventId = Annotated[int | None, Header(alias="Last-Event-ID", ge=0)]
AfterQuery = Annotated[int | None, Query(alias="after", ge=0)]


def stream_timing() -> tuple[float, float, float]:
    """Poll interval, keep-alive interval and maximum stream length, in seconds."""
    settings = get_settings()
    return settings.stream_poll_seconds, settings.stream_heartbeat_seconds, settings.stream_max_seconds


def cursor(header_id: int | None, after: int | None, latest: Callable[[], int]) -> int:
    """Where to start: the browser's Last-Event-ID, else ?after=, else now (live only)."""
    if header_id is not None:
        return header_id
    if after is not None:
        return after
    return latest()


def _fetch_batch(open_session: SessionOpener, fetch: Fetch, after: int) -> list[dict]:
    with open_session() as db:
        return fetch(db, after)


async def event_stream(
    request: Request, open_session: SessionOpener, fetch: Fetch, after: int
) -> AsyncIterator[str]:
    poll, heartbeat, max_seconds = stream_timing()
    started = last_sent = time.monotonic()
    yield "retry: 3000\n\n"  # reconnect delay for the browser
    while time.monotonic() - started < max_seconds:
        if await request.is_disconnected():
            return
        batch = await run_in_threadpool(_fetch_batch, open_session, fetch, after)
        for event in batch:
            after = event["id"]
            yield format_sse(event)
        if batch:
            last_sent = time.monotonic()
        if len(batch) >= PAGE_SIZE:
            continue  # more is waiting; do not sleep
        if time.monotonic() - last_sent >= heartbeat:
            yield ": keep-alive\n\n"  # keeps proxies from closing an idle connection
            last_sent = time.monotonic()
        await asyncio.sleep(poll)


def sse_response(stream: AsyncIterator[str]) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )
