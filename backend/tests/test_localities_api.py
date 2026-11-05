import pytest
from sqlalchemy.orm import Session

from app.seed.catalog import seed_catalog


@pytest.fixture()
def seeded(engine):
    with Session(engine) as db:
        seed_catalog(db)
        db.commit()


def names(response):
    return [row["name"] for row in response.json()]


def test_empty_search_lists_areas_by_city_then_name(client, seeded):
    rows = client.get("/localities", params={"limit": 50}).json()
    assert len(rows) == 16
    assert [(r["city"], r["name"]) for r in rows] == sorted((r["city"], r["name"]) for r in rows)
    assert set(rows[0]) == {"name", "city", "latitude", "longitude"}


def test_search_matches_inside_the_name_ignoring_case(client, seeded):
    # Names that start with the text come first, then the others that contain it.
    assert names(client.get("/localities", params={"q": "kond"})) == ["Kondapur", "Manikonda"]
    assert "HITEC City" in names(client.get("/localities", params={"q": "CITY"}))
    assert names(client.get("/localities", params={"q": "  gachi  "})) == ["Gachibowli"]


def test_wildcard_characters_are_literal(client, seeded):
    assert client.get("/localities", params={"q": "%"}).json() == []
    assert client.get("/localities", params={"q": "_"}).json() == []


def test_limit_and_bounds(client, seeded):
    assert len(client.get("/localities", params={"limit": 3}).json()) == 3
    assert client.get("/localities", params={"limit": 0}).status_code == 422
    assert client.get("/localities", params={"limit": 51}).status_code == 422
    assert client.get("/localities", params={"q": "x" * 61}).status_code == 422
