import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def app_client():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
