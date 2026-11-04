"""Throttle repeated failed sign-ins.

Failures are counted per client address and email together. That slows password
guessing against one account without letting a stranger lock a real customer out
from their own address.

Limits of this version, stated plainly: the counts live in this process's memory,
so they reset when the server restarts and are not shared between instances. That
suits the single-instance deployment this project targets; a shared store such as
Redis would be the next step for several instances.
"""

import time
from collections import deque
from collections.abc import Callable
from functools import lru_cache
from threading import Lock


class LoginThrottle:
    def __init__(
        self,
        max_failures: int = 5,
        window_seconds: float = 15 * 60,
        max_keys: int = 10_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_failures = max_failures
        self._window = window_seconds
        self._max_keys = max_keys
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _recent(self, key: str, now: float) -> deque[float] | None:
        failures = self._failures.get(key)
        if failures is None:
            return None
        while failures and now - failures[0] >= self._window:
            failures.popleft()
        if not failures:
            del self._failures[key]
            return None
        return failures

    def retry_after(self, key: str) -> int:
        """Seconds to wait before this key may try again; 0 if it may try now."""
        with self._lock:
            now = self._clock()
            failures = self._recent(key, now)
            if failures is None or len(failures) < self._max_failures:
                return 0
            return max(1, int(self._window - (now - failures[0])) + 1)

    def record_failure(self, key: str) -> None:
        with self._lock:
            now = self._clock()
            if key not in self._failures and len(self._failures) >= self._max_keys:
                self._make_room(now)
            self._failures.setdefault(key, deque()).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def _make_room(self, now: float) -> None:
        """Keep memory bounded: drop expired keys first, then the least recently failed."""
        for key in list(self._failures):
            self._recent(key, now)
        while len(self._failures) >= self._max_keys:
            oldest = min(self._failures, key=lambda k: self._failures[k][-1])
            del self._failures[oldest]


@lru_cache
def get_login_throttle() -> LoginThrottle:
    return LoginThrottle()
