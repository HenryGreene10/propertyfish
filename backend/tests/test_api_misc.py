import pytest


@pytest.mark.anyio
async def test_health(app_client):
    r = await app_client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


@pytest.mark.anyio
async def test_chat_contract(app_client):
    r = await app_client.post("/api/chat/query", json={"question":"zoning district"})
    assert r.status_code == 200
    j = r.json()
    # minimal contract
    for k in ("question","summary","sources","citations","debug"):
        assert k in j

