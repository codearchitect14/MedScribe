"""Tests for the Phase 9 request body size limit middleware."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio(loop_scope="session")
async def test_oversized_content_length_rejected_before_body_is_read():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/contact-requests",
            content=b"x",
            headers={"Content-Length": str(100 * 1024 * 1024), "Content-Type": "application/json"},
        )
        assert response.status_code == 413
        assert response.json()["detail"] == "Request body too large"


@pytest.mark.asyncio(loop_scope="session")
async def test_normal_sized_request_is_unaffected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
