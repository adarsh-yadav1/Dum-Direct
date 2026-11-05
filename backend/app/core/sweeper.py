"""Background task that flags late orders even when nobody has the board open."""

import asyncio
import logging
from collections.abc import Callable

from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.clock import utcnow
from app.services.kitchen import sweep_late_orders

log = logging.getLogger(__name__)


def sweep_once(open_session: Callable[[], Session]) -> int:
    with open_session() as db:
        return len(sweep_late_orders(db, utcnow()))


async def run_sweeper(open_session: Callable[[], Session], interval_seconds: float) -> None:
    """Sweep every interval. A failed sweep is logged and retried, never fatal. Safe to run on
    several instances at once: an order is flagged once however many sweepers see it."""
    while True:
        try:
            await run_in_threadpool(sweep_once, open_session)
        except Exception:  # noqa: BLE001
            log.exception("late-order sweep failed")
        await asyncio.sleep(interval_seconds)
