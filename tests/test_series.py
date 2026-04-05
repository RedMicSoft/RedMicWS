import pytest
from httpx import AsyncClient


@pytest.mark.parametrize("auth_headers", [{"level": 1}], indirect=True)
async def test_series_endpoint(auth_headers: dict, client: AsyncClient):
    response = await client.get("/series/", headers=auth_headers)
    assert response.status_code == 404
    assert response.json() == {"detail": "В данном проекте ещё нет серий."}
