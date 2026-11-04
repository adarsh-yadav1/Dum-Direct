import fakeredis
import pytest
import redis

from app.core.config import get_settings
from app.core.rate_limit import (
    LoginThrottle,
    RedisLoginThrottle,
    ResilientThrottle,
    get_login_throttle,
)


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def make(server: fakeredis.FakeServer, clock: Clock, **kwargs) -> RedisLoginThrottle:
    return RedisLoginThrottle(fakeredis.FakeRedis(server=server), clock=clock, **kwargs)


def test_blocks_after_the_limit_and_lifts_when_failures_age_out():
    clock = Clock()
    throttle = make(fakeredis.FakeServer(), clock, max_failures=3, window_seconds=600)
    for _ in range(2):
        throttle.record_failure("a")
    assert throttle.retry_after("a") == 0
    throttle.record_failure("a")
    assert 1 <= throttle.retry_after("a") <= 601
    clock.now += 601
    assert throttle.retry_after("a") == 0


def test_keys_are_independent_and_reset_clears_one():
    throttle = make(fakeredis.FakeServer(), Clock(), max_failures=1)
    throttle.record_failure("a")
    assert throttle.retry_after("a") > 0 and throttle.retry_after("b") == 0
    throttle.reset("a")
    assert throttle.retry_after("a") == 0


def test_two_server_instances_share_the_same_counts():
    server, clock = fakeredis.FakeServer(), Clock()
    first, second = make(server, clock, max_failures=2), make(server, clock, max_failures=2)
    first.record_failure("1.2.3.4|asha@example.com")
    second.record_failure("1.2.3.4|asha@example.com")
    assert first.retry_after("1.2.3.4|asha@example.com") > 0  # failures made on the other instance count


def test_no_email_or_address_is_stored_in_the_clear():
    server = fakeredis.FakeServer()
    throttle = make(server, Clock())
    throttle.record_failure("203.0.113.7|asha@example.com")
    names = [name.decode() for name in fakeredis.FakeRedis(server=server).keys("*")]
    assert names and all("asha" not in n and "203.0.113" not in n for n in names)


# ----- fallback when Redis is down ---------------------------------------------


class Broken:
    def __init__(self) -> None:
        self.calls = 0

    def _fail(self, *_: object):
        self.calls += 1
        raise redis.ConnectionError("down")

    retry_after = record_failure = reset = _fail


def test_a_redis_outage_falls_back_to_memory_and_still_blocks():
    broken, clock = Broken(), Clock()
    memory = LoginThrottle(max_failures=2, clock=clock)
    throttle = ResilientThrottle(broken, memory, pause_seconds=30, clock=clock)
    assert throttle.retry_after("a") == 0  # no exception reaches the caller
    throttle.record_failure("a")
    throttle.record_failure("a")
    assert throttle.retry_after("a") > 0  # memory is protecting while Redis is down


def test_a_down_redis_is_left_alone_for_a_while_and_then_tried_again():
    broken, clock = Broken(), Clock()
    throttle = ResilientThrottle(broken, LoginThrottle(clock=clock), pause_seconds=30, clock=clock)
    for _ in range(5):
        throttle.retry_after("a")
    assert broken.calls == 1  # not one connection attempt per request
    clock.now += 31
    throttle.retry_after("a")
    assert broken.calls == 2


def test_without_a_redis_url_the_throttle_lives_in_memory(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REDIS_URL", "")
    get_settings.cache_clear()
    get_login_throttle.cache_clear()
    try:
        assert isinstance(get_login_throttle(), LoginThrottle)
    finally:
        get_settings.cache_clear()
        get_login_throttle.cache_clear()
