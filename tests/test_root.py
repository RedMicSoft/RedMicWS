from httpx import AsyncClient


async def test_root_returns_welcome(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome!"}
