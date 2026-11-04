from collections.abc import Iterator

import pytest
from argon2 import PasswordHasher
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.api.auth import router as auth_router
from app.api.deps import outlet_staff, require_roles
from app.core.db import get_db
from app.models import Order, User
from app.models.enums import Role
from app.services.access import can_access_outlet, can_override_estimate, can_view_order
from tests.factories import make_outlet, make_user

PASSWORD = "correct-horse-1"
CHEAP = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)


def person(role: str, user_id: int = 1, outlet_id: int | None = None) -> User:
    return User(id=user_id, role=role, outlet_id=outlet_id)


# ----- the rules --------------------------------------------------------------


@pytest.mark.parametrize(
    ("user", "outlet_id", "allowed"),
    [
        (person("admin"), 1, True),
        (person("admin"), 2, True),
        (person("kitchen", outlet_id=1), 1, True),
        (person("kitchen", outlet_id=1), 2, False),
        (person("manager", outlet_id=1), 1, True),
        (person("manager", outlet_id=1), 2, False),
        (person("customer"), 1, False),
    ],
)
def test_outlet_access(user: User, outlet_id: int, allowed: bool):
    assert can_access_outlet(user, outlet_id) is allowed


@pytest.mark.parametrize(
    ("user", "allowed"),
    [
        (person("admin"), True),
        (person("manager", outlet_id=1), True),
        (person("manager", outlet_id=2), False),
        (person("kitchen", outlet_id=1), False),  # the manager owns the promise
        (person("customer"), False),
    ],
)
def test_only_the_outlets_manager_or_an_admin_may_override_an_estimate(user: User, allowed: bool):
    assert can_override_estimate(user, 1) is allowed


@pytest.mark.parametrize(
    ("user", "allowed"),
    [
        (person("customer", user_id=7), True),  # the order's own customer
        (person("customer", user_id=8), False),  # another customer
        (person("kitchen", user_id=9, outlet_id=1), True),
        (person("kitchen", user_id=9, outlet_id=2), False),
        (person("admin", user_id=10), True),
    ],
)
def test_who_may_view_an_order(user: User, allowed: bool):
    order = Order(user_id=7, outlet_id=1)
    assert can_view_order(user, order) is allowed


# ----- the same rules, enforced on real requests ------------------------------


@pytest.fixture()
def http(engine: Engine) -> Iterator[TestClient]:
    """A small app that uses the dependencies exactly as the real routes will."""
    app = FastAPI()
    app.include_router(auth_router)

    @app.get("/outlets/{outlet_id}/orders")
    def outlet_orders(outlet_id: int, _: User = Depends(outlet_staff)) -> dict:
        return {"outlet_id": outlet_id}

    @app.get("/admin/menu")
    def admin_menu(_: User = Depends(require_roles(Role.ADMIN))) -> dict:
        return {"ok": True}

    def override_db() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with Session(engine) as db:
        one = make_outlet(db, name="Outlet One", fssai_no="99999000000101")
        two = make_outlet(db, name="Outlet Two", fssai_no="99999000000102")
        accounts = [
            ("customer@example.com", "customer", None),
            ("kitchen1@example.com", "kitchen", one.id),
            ("manager1@example.com", "manager", one.id),
            ("admin@example.com", "admin", None),
        ]
        for email, role, outlet_id in accounts:
            make_user(db, email=email, role=role, outlet_id=outlet_id, password_hash=CHEAP.hash(PASSWORD))
        db.commit()
        app.state.outlets = (one.id, two.id)
    with TestClient(app) as client:
        client.outlets = app.state.outlets  # type: ignore[attr-defined]
        yield client


def sign_in(client: TestClient, email: str) -> None:
    assert client.post("/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200


def test_signed_out_visitors_get_401(http: TestClient):
    one, _ = http.outlets  # type: ignore[attr-defined]
    assert http.get(f"/outlets/{one}/orders").status_code == 401
    assert http.get("/admin/menu").status_code == 401


def test_a_customer_cannot_use_outlet_or_admin_routes(http: TestClient):
    one, _ = http.outlets  # type: ignore[attr-defined]
    sign_in(http, "customer@example.com")
    assert http.get(f"/outlets/{one}/orders").status_code == 403
    assert http.get("/admin/menu").status_code == 403


@pytest.mark.parametrize("email", ["kitchen1@example.com", "manager1@example.com"])
def test_outlet_staff_reach_their_own_outlet_and_not_another(http: TestClient, email: str):
    one, two = http.outlets  # type: ignore[attr-defined]
    sign_in(http, email)
    assert http.get(f"/outlets/{one}/orders").json() == {"outlet_id": one}
    other = http.get(f"/outlets/{two}/orders")
    assert other.status_code == 403
    assert http.get("/admin/menu").status_code == 403


def test_an_admin_reaches_every_outlet_and_the_menu_admin(http: TestClient):
    one, two = http.outlets  # type: ignore[attr-defined]
    sign_in(http, "admin@example.com")
    assert http.get(f"/outlets/{one}/orders").status_code == 200
    assert http.get(f"/outlets/{two}/orders").status_code == 200
    assert http.get("/admin/menu").status_code == 200
