from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_origins_are_split_and_trimmed():
    settings = Settings(cors_origins="http://a.test, http://b.test ,")
    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


def test_unknown_environment_is_rejected():
    try:
        Settings(env="staging")
    except ValueError:
        return
    raise AssertionError("an unknown ENV value should be rejected")
