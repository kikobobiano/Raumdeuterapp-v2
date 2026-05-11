from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}


def test_seasons() -> None:
    with TestClient(app) as c:
        r = c.get("/meta/seasons")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
