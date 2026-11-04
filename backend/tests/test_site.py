from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.main import app as api
from app.site import create_site


@pytest.fixture()
def static_dir(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html><body>DumDirect web</body></html>")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log('app')")
    (tmp_path / "favicon.svg").write_text("<svg/>")
    return tmp_path


@pytest.fixture()
def web(static_dir: Path, engine: Engine) -> Iterator[TestClient]:
    def override_db() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as db:
            yield db

    api.dependency_overrides[get_db] = override_db
    with TestClient(create_site(str(static_dir))) as client:
        yield client
    api.dependency_overrides.clear()


def test_the_home_page_is_the_web_app_and_is_never_cached(web: TestClient):
    response = web.get("/")
    assert response.status_code == 200 and "DumDirect web" in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_a_deep_link_gets_the_web_app_so_a_reload_does_not_404(web: TestClient):
    response = web.get("/orders/778120")
    assert response.status_code == 200 and "DumDirect web" in response.text


def test_hashed_assets_are_cached_for_a_year(web: TestClient):
    response = web.get("/assets/app-abc123.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


def test_a_missing_file_is_a_404_and_not_the_web_app(web: TestClient):
    assert web.get("/assets/old-build.js").status_code == 404


def test_the_api_lives_under_api_and_unknown_api_paths_are_json_404s(web: TestClient):
    assert web.get("/api/health").json() == {"status": "ok"}
    missing = web.get("/api/no-such-route")
    assert missing.status_code == 404 and missing.headers["content-type"] == "application/json"


def test_every_response_carries_the_hardening_headers(web: TestClient):
    for path in ("/", "/api/health"):
        headers = web.get(path).headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_the_web_apps_own_sign_in_request_passes_the_origin_check(web: TestClient):
    response = web.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "whatever-1"},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 401  # refused for its credentials, not its origin


def test_without_a_built_web_app_the_site_serves_the_api_alone():
    with TestClient(create_site("")) as client:
        assert client.get("/api/health").status_code == 200
        assert client.get("/").status_code == 404
