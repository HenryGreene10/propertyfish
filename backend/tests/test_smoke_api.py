import os

# Ensure tests use the same DB your app uses
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/propertyfish"
)

from starlette.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def test_health():
    with TestClient(app) as c:
        r = c.get("/health")
        assert r.status_code == 200
        assert r.json().get("ok") is True


def test_search_basic():
    with TestClient(app) as c:
        r = c.get("/api/search", params={"borough": "QN", "limit": 3})
        assert r.status_code == 200
        data = r.json()
        assert "total" in data and "rows" in data
        assert isinstance(data["rows"], list)
