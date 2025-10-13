import pytest
from httpx import AsyncClient

# Assumes DB seeded with BBL 1000000001 and 123 MAIN ST
BBL = "1000000001"
ADDR = "123 MAIN ST"


@pytest.mark.anyio
async def test_chat_permits_by_bbl(app_client: AsyncClient):
    res = await app_client.post("/api/chat/query", json={"question": f"show permits for {BBL}"})
    assert res.status_code == 200
    j = res.json()
    assert "Permits:" in j["summary"]
    assert any(c.get("table") == "dob_permits" for c in j.get("citations", []))


@pytest.mark.anyio
async def test_chat_violations_by_address(app_client: AsyncClient):
    res = await app_client.post("/api/chat/query", json={"question": f"any violations at {ADDR} NY?"})
    assert res.status_code == 200
    j = res.json()
    assert "Violations:" in j["summary"]
    assert any(c.get("table") == "dob_violations" for c in j.get("citations", []))


@pytest.mark.anyio
async def test_chat_zoning_with_context(app_client: AsyncClient):
    res = await app_client.post("/api/chat/query", json={"question": "zoning district", "context_bbl": BBL})
    assert res.status_code == 200
    assert "Zoning:" in res.json()["summary"]


@pytest.mark.anyio
async def test_chat_properties_fallback(app_client: AsyncClient):
    res = await app_client.post("/api/chat/query", json={"question": "who is the owner?", "context_bbl": BBL})
    assert res.status_code == 200
    assert "Property:" in res.json()["summary"]


@pytest.mark.anyio
async def test_chat_no_hits_path_is_graceful(app_client: AsyncClient):
    res = await app_client.post("/api/chat/query", json={"question": "purple giraffes zoning?"})
    assert res.status_code == 200
    assert "No matching" in res.json()["summary"]
