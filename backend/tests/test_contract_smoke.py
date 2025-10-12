from fastapi.testclient import TestClient
from app.main import app


def test_summary_200_with_sources(monkeypatch):
    from app.routers import property as property_router

    def fake_get_summary_by_bbl(bbl: str):
        return {
            "bbl": bbl,
            "address": "6 E 43rd St, New York, NY 10017",
            "borough": "Manhattan",
            "block": 1277,
            "lot": 8,
            "bin": 1234567,
            "land_use": "4",
            "tax_class": "4",
            "lot_area_sqft": 17795,
            "bldg_sqft": 304525,
            "stories": 27,
            "year_built": 1968,
            "last_updated": "2025-01-01T00:00:00Z",
        }

    monkeypatch.setattr(property_router, "get_summary_by_bbl", fake_get_summary_by_bbl)

    client = TestClient(app)
    r = client.get("/property/1012700008/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["bbl"] == "1012700008"
    assert data["sources"][0]["name"].startswith("PLUTO")


def test_resolve_returns_candidate(monkeypatch):
    from app.routers import resolve as resolve_router

    def fake_resolve_candidates(q: str, limit: int = 5):
        return [{"bbl": "1012700008", "address_std": "6 E 43rd St, New York, NY 10017"}]

    monkeypatch.setattr(resolve_router, "resolve_candidates", fake_resolve_candidates)

    client = TestClient(app)
    r = client.get("/resolve", params={"query": "6 E 43rd"})
    assert r.status_code == 200
    data = r.json()
    assert any(c["bbl"] == "1012700008" for c in data.get("candidates", []))


def test_deeds_endpoint_sorted_and_limited(monkeypatch):
    from app.routers import property as property_router

    def fake_get_deeds_by_bbl(bbl: str, limit: int):
        return [
            {
                "recorded_at": "2022-06-15",
                "consideration": 150000000,
                "parties": {"party_1": "ABC LLC", "party_2": "XYZ LLC"},
                "doc_id": "202206150123",
                "doc_url": "https://a836-acris.nyc.gov/DS/DocumentSearch/DocumentImageView?doc_id=202206150123",
            },
            {
                "recorded_at": "2018-03-20",
                "consideration": 95000000,
                "parties": {"party_1": "Old Owner LLC", "party_2": "New Owner LLC"},
                "doc_id": "201803200987",
                "doc_url": "https://a836-acris.nyc.gov/DS/DocumentSearch/DocumentImageView?doc_id=201803200987",
            },
        ][:limit]

    monkeypatch.setattr(property_router, "get_deeds_by_bbl", fake_get_deeds_by_bbl)

    client = TestClient(app)
    r = client.get("/property/1012700008/deeds", params={"limit": 2})
    assert r.status_code == 200
    data = r.json()
    rows = data.get("rows", [])
    assert len(rows) <= 2
    # ensure sorted desc by recorded_at
    dates = [row["recorded_at"] for row in rows]
    assert dates == sorted(dates, reverse=True)
    assert all("doc_url" in row and row["doc_url"] for row in rows)


def test_mortgages_endpoint_sorted_and_limited(monkeypatch):
    from app.routers import property as property_router

    def fake_get_mortgages_by_bbl(bbl: str, limit: int):
        return [
            {
                "recorded_at": "2022-06-15",
                "consideration": 120000000,
                "parties": {"party_1": "XYZ LLC", "party_2": "Big Bank N.A."},
                "doc_id": "202206150456",
                "doc_url": "https://a836-acris.nyc.gov/DS/DocumentSearch/DocumentImageView?doc_id=202206150456",
            }
        ][:limit]

    monkeypatch.setattr(property_router, "get_mortgages_by_bbl", fake_get_mortgages_by_bbl)

    client = TestClient(app)
    r = client.get("/property/1012700008/mortgages", params={"limit": 2})
    assert r.status_code == 200
    data = r.json()
    rows = data.get("rows", [])
    assert len(rows) <= 2
    dates = [row["recorded_at"] for row in rows]
    assert dates == sorted(dates, reverse=True)
    assert all("doc_url" in row and row["doc_url"] for row in rows)
