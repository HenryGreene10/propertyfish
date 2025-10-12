import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from backend.app.main import app

from fastapi.testclient import TestClient
from backend.app.main import app


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


def test_permits_endpoint_has_filed_at(monkeypatch):
    from app.routers import property as property_router

    def fake_get_permits_by_bbl(bbl: str, since: str | None = None):
        return [
            {"filed_at": "2025-06-01", "details": {"job_type": "Alteration", "status": "Permit - Issued", "description": "HVAC replacement", "initial_cost": 120000}},
            {"filed_at": "2024-12-11", "details": {"job_type": "Alteration CO", "status": "Issued", "description": "CO for lobby", "initial_cost": 250000}},
        ]

    monkeypatch.setattr(property_router, "get_permits_by_bbl", fake_get_permits_by_bbl)

    client = TestClient(app)
    r = client.get("/property/1012700008/permits")
    assert r.status_code == 200
    data = r.json()
    rows = data.get("rows", [])
    assert len(rows) >= 1
    assert "filed_at" in rows[0]


def test_violations_endpoint_has_issued_at(monkeypatch):
    from app.routers import property as property_router

    def fake_get_violations_by_bbl(bbl: str, since: str | None = None):
        return [
            {"issued_at": "2025-01-22", "details": {"code": "DOB-YY", "status": "Open", "description": "Guardrail not to code"}},
            {"issued_at": "2024-10-18", "details": {"code": "ECB-XX", "status": "Resolved", "description": "Boiler violation resolved"}},
        ]

    monkeypatch.setattr(property_router, "get_violations_by_bbl", fake_get_violations_by_bbl)

    client = TestClient(app)
    r = client.get("/property/1012700008/violations")
    assert r.status_code == 200
    data = r.json()
    rows = data.get("rows", [])
    assert len(rows) >= 1
    assert "issued_at" in rows[0]


def test_zoning_endpoint_has_base_codes(monkeypatch):
    from app.routers import property as property_router

    def fake_get_zoning_by_bbl(bbl: str):
        return {"base_codes": ["C5-3"], "overlays": ["Special Midtown District"], "sp_districts": ["SP-MID"], "far_notes": "See §81-00 et seq"}

    monkeypatch.setattr(property_router, "get_zoning_by_bbl", fake_get_zoning_by_bbl)

    client = TestClient(app)
    r = client.get("/property/1012700008/zoning")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("base", []), list)
    assert len(data.get("base", [])) >= 1
