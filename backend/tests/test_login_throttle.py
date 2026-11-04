from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.rate_limit import LoginThrottle
from tests.factories import make_user

PASSWORD = "correct-horse-1"
CHEAP = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


# ----- the throttle itself ----------------------------------------------------


def test_blocks_after_the_limit_and_says_how_long_to_wait():
    clock = Clock()
    throttle = LoginThrottle(max_failures=3, window_seconds=600, clock=clock)
    for _ in range(2):
        throttle.record_failure("a")
    assert throttle.retry_after("a") == 0
    throttle.record_failure("a")
    assert 1 <= throttle.retry_after("a") <= 601
    clock.now += 300
    assert 1 <= throttle.retry_after("a") <= 301


def test_the_block_lifts_when_the_failures_age_out():
    clock = Clock()
    throttle = LoginThrottle(max_failures=2, window_seconds=600, clock=clock)
    throttle.record_failure("a")
    throttle.record_failure("a")
    assert throttle.retry_after("a") > 0
    clock.now += 601
    assert throttle.retry_after("a") == 0


def test_keys_are_independent_and_reset_clears_one():
    throttle = LoginThrottle(max_failures=1, clock=Clock())
    throttle.record_failure("a")
    assert throttle.retry_after("a") > 0 and throttle.retry_after("b") == 0
    throttle.reset("a")
    assert throttle.retry_after("a") == 0


def test_memory_stays_bounded():
    clock = Clock()
    throttle = LoginThrottle(max_keys=100, clock=clock)
    for index in range(1000):
        clock.now += 0.001
        throttle.record_failure(f"key-{index}")
    assert len(throttle._failures) <= 100  # noqa: SLF001


# ----- on the real endpoint ---------------------------------------------------


def login(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_five_wrong_passwords_block_even_the_right_one(client: TestClient, session: Session):
    make_user(session, email="asha@example.com", password_hash=CHEAP.hash(PASSWORD))
    session.commit()

    for _ in range(5):
        assert login(client, "asha@example.com", "wrong-wrong-1").status_code == 401
    blocked = login(client, "asha@example.com", PASSWORD)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert "too many" in blocked.json()["detail"].lower()


def test_another_email_from_the_same_address_is_not_blocked(client: TestClient, session: Session):
    make_user(session, email="asha@example.com", password_hash=CHEAP.hash(PASSWORD))
    make_user(session, email="ravi@example.com", password_hash=CHEAP.hash(PASSWORD))
    session.commit()
    for _ in range(5):
        login(client, "asha@example.com", "wrong-wrong-1")
    assert login(client, "ravi@example.com", PASSWORD).status_code == 200


def test_a_successful_login_clears_the_count(client: TestClient, session: Session):
    make_user(session, email="asha@example.com", password_hash=CHEAP.hash(PASSWORD))
    session.commit()
    for _ in range(4):
        login(client, "asha@example.com", "wrong-wrong-1")
    assert login(client, "asha@example.com", PASSWORD).status_code == 200
    for _ in range(4):
        assert login(client, "asha@example.com", "wrong-wrong-1").status_code == 401
