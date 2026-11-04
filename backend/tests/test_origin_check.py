from fastapi.testclient import TestClient

LOGIN = {"email": "nobody@example.com", "password": "whatever-1"}


def test_a_write_from_an_unknown_site_is_refused(client: TestClient):
    response = client.post("/auth/login", json=LOGIN, headers={"Origin": "http://evil.example"})
    assert response.status_code == 403
    assert response.json() == {"detail": "Origin not allowed."}


def test_a_write_from_the_web_app_gets_through_to_the_route(client: TestClient):
    response = client.post("/auth/login", json=LOGIN, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 401  # reached the route, which refused the credentials


def test_a_write_with_no_origin_is_not_a_browser_acting_for_another_site(client: TestClient):
    assert client.post("/auth/login", json=LOGIN).status_code == 401


def test_reads_are_never_blocked_by_origin(client: TestClient):
    assert client.get("/health", headers={"Origin": "http://evil.example"}).status_code == 200


# ----- the site's own origin ---------------------------------------------------


def test_a_write_from_the_servers_own_origin_is_allowed(client: TestClient):
    # Browsers send Origin on the site's own writes too. The test client addresses "testserver".
    response = client.post("/auth/login", json=LOGIN, headers={"Origin": "http://testserver"})
    assert response.status_code == 401  # reached the route


def test_look_alike_origins_are_refused(client: TestClient):
    for origin in (
        "http://testserver.evil.example",
        "http://testserver:8000",
        "http://evil.example/testserver",
        "null",
    ):
        response = client.post("/auth/login", json=LOGIN, headers={"Origin": origin})
        assert response.status_code == 403, origin
