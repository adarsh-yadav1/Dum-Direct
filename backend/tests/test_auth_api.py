import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import needs_rehash, verify_password
from app.core.tokens import SESSION_COOKIE_NAME, create_session_token
from app.models import User
from tests.factories import make_user

# Cheap hashes keep these tests fast; the login code verifies hashes of any strength.
CHEAP = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
PASSWORD = "correct-horse-1"
REGISTER = {"name": "Asha Rao", "email": "Asha@Example.com", "password": "a-long-password"}


def add_user(db: Session, email: str = "asha@example.com", **overrides) -> User:
    user = make_user(db, email=email, password_hash=CHEAP.hash(PASSWORD), **overrides)
    db.commit()
    return user


def stored(db: Session, email: str) -> User:
    db.expire_all()
    return db.scalars(select(User).where(User.email == email)).one()


# ----- register --------------------------------------------------------------


def test_register_creates_a_customer_and_signs_them_in(client: TestClient, session: Session):
    response = client.post("/auth/register", json=REGISTER)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "email", "name", "role", "outlet_id", "marketing_opt_in"}
    assert (body["email"], body["role"], body["outlet_id"]) == ("asha@example.com", "customer", None)
    assert client.get("/auth/me").json()["email"] == "asha@example.com"

    user = stored(session, "asha@example.com")
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(REGISTER["password"], user.password_hash)


def test_session_cookie_is_http_only_and_same_site(client: TestClient):
    cookie = client.post("/auth/register", json=REGISTER).headers["set-cookie"].lower()
    assert cookie.startswith(f"{SESSION_COOKIE_NAME}=")
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie


def test_a_client_cannot_choose_its_own_role(client: TestClient):
    response = client.post("/auth/register", json={**REGISTER, "role": "admin"})
    assert response.status_code == 422


def test_marketing_opt_in_is_off_by_default_and_timestamped_when_given(
    client: TestClient, session: Session
):
    client.post("/auth/register", json=REGISTER)
    client.post(
        "/auth/register",
        json={**REGISTER, "email": "opted@example.com", "marketing_opt_in": True},
    )
    plain, opted = stored(session, "asha@example.com"), stored(session, "opted@example.com")
    assert (plain.marketing_opt_in, plain.marketing_opt_in_at) == (False, None)
    assert opted.marketing_opt_in and opted.marketing_opt_in_at is not None


def test_a_second_account_with_the_same_email_is_refused_whatever_the_case(client: TestClient):
    assert client.post("/auth/register", json=REGISTER).status_code == 201
    again = client.post("/auth/register", json={**REGISTER, "email": "ASHA@EXAMPLE.COM"})
    assert again.status_code == 409


@pytest.mark.parametrize(
    "bad",
    [
        {"password": "short"},
        {"password": "x" * 129},
        {"phone": "12345"},
        {"phone": "5123456789"},  # Indian mobiles start with 6 to 9
        {"email": "not-an-email"},
        {"name": "   "},
    ],
)
def test_invalid_registrations_are_rejected(client: TestClient, bad: dict):
    assert client.post("/auth/register", json={**REGISTER, **bad}).status_code == 422


def test_a_blank_phone_is_treated_as_none(client: TestClient, session: Session):
    assert client.post("/auth/register", json={**REGISTER, "phone": " "}).status_code == 201
    assert stored(session, "asha@example.com").phone is None


# ----- login, logout, me -----------------------------------------------------


def test_login_with_the_right_password_signs_in_whatever_the_email_case(
    client: TestClient, session: Session
):
    add_user(session)
    response = client.post("/auth/login", json={"email": "Asha@EXAMPLE.com", "password": PASSWORD})
    assert response.status_code == 200
    assert client.get("/auth/me").json()["email"] == "asha@example.com"


def test_wrong_password_and_unknown_email_give_the_same_answer(client: TestClient, session: Session):
    add_user(session)
    wrong = client.post("/auth/login", json={"email": "asha@example.com", "password": "nope-nope-1"})
    unknown = client.post("/auth/login", json={"email": "who@example.com", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json() == {"detail": "Invalid email or password."}
    assert SESSION_COOKIE_NAME not in wrong.headers.get("set-cookie", "")


def test_an_old_weak_hash_is_upgraded_after_a_correct_login(client: TestClient, session: Session):
    before = add_user(session).password_hash
    assert needs_rehash(before)
    client.post("/auth/login", json={"email": "asha@example.com", "password": PASSWORD})
    after = stored(session, "asha@example.com").password_hash
    assert after != before and not needs_rehash(after) and verify_password(PASSWORD, after)


def test_logout_ends_the_session(client: TestClient, session: Session):
    add_user(session)
    client.post("/auth/login", json={"email": "asha@example.com", "password": PASSWORD})
    assert client.get("/auth/me").status_code == 200
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_me_needs_a_valid_session(client: TestClient):
    assert client.get("/auth/me").status_code == 401
    client.cookies.set(SESSION_COOKIE_NAME, "garbage")
    assert client.get("/auth/me").status_code == 401


def test_a_token_for_a_user_that_no_longer_exists_is_signed_out(client: TestClient):
    client.cookies.set(SESSION_COOKIE_NAME, create_session_token(9999))
    assert client.get("/auth/me").status_code == 401
