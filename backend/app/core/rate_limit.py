"""Throttle repeated failed sign-ins.

Failures are counted per client address and email together. That slows password
guessing against one account without letting a stranger lock a real customer out
from their own address.

Where the counts live: in Redis when REDIS_URL is set, so every server instance
sees the same failures and a restart does not forget them. Without Redis, or while
Redis is unreachable, they live in this process's memory instead. That still protects
a single instance, but its counts reset on restart and are not shared.
"""

import hashlib
import logging
import time
import uuid
from collections import deque
from collections.abc import Callable
from functools import lru_cache
from threading import Lock
from typing import Protocol

import redis

from app.core.config import get_settings

log = logging.getLogger(__name__)


class Throttle(Protocol):
    def retry_after(self, key: str) -> int: ...
    def record_failure(self, key: str) -> None: ...
    def reset(self, key: str) -> None: ...


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


class RedisLoginThrottle:
    """The same sliding window, kept in a Redis sorted set per key.

    Keys are hashed, so no email address or client address is stored in Redis in the clear.
    """

    def __init__(
        self,
        client: redis.Redis,
        max_failures: int = 5,
        window_seconds: float = 15 * 60,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._redis = client
        self._max_failures = max_failures
        self._window = window_seconds
        self._clock = clock

    @staticmethod
    def _name(key: str) -> str:
        return "login-failures:" + hashlib.sha256(key.encode()).hexdigest()

    def retry_after(self, key: str) -> int:
        now = self._clock()
        name = self._name(key)
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(name, 0, now - self._window)
        pipe.zcard(name)
        pipe.zrange(name, 0, 0, withscores=True)
        _, count, oldest = pipe.execute()
        if count < self._max_failures:
            return 0
        return max(1, int(self._window - (now - oldest[0][1])) + 1)

    def record_failure(self, key: str) -> None:
        now = self._clock()
        name = self._name(key)
        pipe = self._redis.pipeline()
        pipe.zadd(name, {f"{now}:{uuid.uuid4().hex}": now})
        pipe.expire(name, int(self._window) + 1)
        pipe.execute()

    def reset(self, key: str) -> None:
        self._redis.delete(self._name(key))


class ResilientThrottle:
    """Use the shared store, but never let its failure break sign-in.

    If Redis errors, protection continues from process memory, and Redis is left alone
    for a while so each request does not wait on a dead connection.
    """

    def __init__(
        self,
        shared: Throttle,
        fallback: Throttle,
        pause_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._shared = shared
        self._fallback = fallback
        self._pause = pause_seconds
        self._clock = clock
        self._shared_down_until = 0.0

    def _call(self, method: str, key: str):
        now = self._clock()
        if now >= self._shared_down_until:
            try:
                return getattr(self._shared, method)(key)
            except redis.RedisError:
                log.warning("Redis unavailable; sign-in throttling uses process memory for %ss", self._pause)
                self._shared_down_until = now + self._pause
        return getattr(self._fallback, method)(key)

    def retry_after(self, key: str) -> int:
        return self._call("retry_after", key)

    def record_failure(self, key: str) -> None:
        self._call("record_failure", key)

    def reset(self, key: str) -> None:
        self._call("reset", key)


@lru_cache
def get_login_throttle() -> Throttle:
    memory = LoginThrottle()
    url = get_settings().redis_url
    if not url:
        return memory
    client = redis.Redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
    return ResilientThrottle(RedisLoginThrottle(client), memory)
