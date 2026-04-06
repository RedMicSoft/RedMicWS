from httpx import AsyncClient

from fastapi import status


async def test_root_returns_welcome(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"message": "Welcome!"}
