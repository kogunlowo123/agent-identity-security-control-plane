"""
Integration tests for the API identity flow.

These tests use httpx AsyncClient with the FastAPI TestClient pattern.
They mock external dependencies (broker, OPA, database) to avoid real I/O.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport

# Add API src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "services" / "api" / "src"))

from api.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing the FastAPI app."""
    async with AsyncClient(
        transport=ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as c:
        yield c


def _make_broker_token_response(spiffe_id: str, tier: str) -> dict:
    """Create a mock broker token issue response."""
    now = int(time.time())
    jti = str(uuid.uuid4())
    return {
        "access_token": "eyJhbGciOiJSUzI1NiJ9.mock.signature",
        "token_type": "Bearer",
        "expires_in": 1800,
        "jti": jti,
        "tier": tier,
        "sub": spiffe_id,
        "scope": f"tier:{tier}",
    }


# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """GET /api/v1/health should always return 200."""
        response = await client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client: AsyncClient) -> None:
        """Health endpoint requires no authentication."""
        response = await client.get("/api/v1/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_readiness_returns_json(self, client: AsyncClient) -> None:
        """GET /api/v1/readiness returns JSON with checks."""
        # Mock all dependency checks to succeed
        with (
            patch("api.routes.v1.health.psycopg2") as mock_pg,
            patch("api.routes.v1.health.httpx.AsyncClient") as mock_httpx,
        ):
            mock_conn = MagicMock()
            mock_pg.connect.return_value = mock_conn

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_http_client = AsyncMock()
            mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
            mock_http_client.__aexit__ = AsyncMock(return_value=None)
            mock_http_client.get = AsyncMock(return_value=mock_resp)
            mock_httpx.return_value = mock_http_client

            response = await client.get("/api/v1/readiness")

        assert response.status_code in (200, 503)
        data = response.json()
        assert "status" in data
        assert "checks" in data
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# Identity issuance tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestIdentityIssuance:
    TRUST_DOMAIN = "agent-identity-security-control-plane"

    @pytest.mark.asyncio
    async def test_issue_valid_identity_returns_201(self, client: AsyncClient) -> None:
        """POST /api/v1/identities/issue with valid payload returns 201."""
        spiffe_id = f"spiffe://{self.TRUST_DOMAIN}/identity-auditor"
        mock_response = _make_broker_token_response(spiffe_id, "T1")

        with patch("api.routes.v1.identities.httpx.AsyncClient") as mock_httpx:
            mock_resp = AsyncMock()
            mock_resp.status_code = 201
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = MagicMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client_instance.post = AsyncMock(return_value=mock_resp)
            mock_httpx.return_value = mock_client_instance

            response = await client.post(
                "/api/v1/identities/issue",
                json={
                    "spiffe_id": spiffe_id,
                    "tier": "T1",
                    "agent_id": "identity-auditor",
                },
            )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "access_token" in data
        assert data["tier"] == "T1"
        assert data["sub"] == spiffe_id

    @pytest.mark.asyncio
    async def test_issue_invalid_spiffe_id_returns_422(self, client: AsyncClient) -> None:
        """POST with invalid SPIFFE ID (missing scheme) returns 422."""
        response = await client.post(
            "/api/v1/identities/issue",
            json={
                "spiffe_id": "not-a-spiffe-id",
                "tier": "T1",
                "agent_id": "test-agent",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_issue_invalid_tier_returns_422(self, client: AsyncClient) -> None:
        """POST with invalid tier returns 422."""
        response = await client.post(
            "/api/v1/identities/issue",
            json={
                "spiffe_id": f"spiffe://{self.TRUST_DOMAIN}/test",
                "tier": "T9",
                "agent_id": "test-agent",
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_issue_missing_required_field_returns_422(self, client: AsyncClient) -> None:
        """POST missing agent_id returns 422."""
        response = await client.post(
            "/api/v1/identities/issue",
            json={
                "spiffe_id": f"spiffe://{self.TRUST_DOMAIN}/test",
                "tier": "T1",
                # agent_id missing
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# Token validation tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestTokenValidation:
    @pytest.mark.asyncio
    async def test_validate_with_invalid_jwt_format_returns_200_invalid(
        self, client: AsyncClient
    ) -> None:
        """POST /validate with malformed token returns valid=False."""
        with patch("api.routes.v1.identities.get_jwks") as mock_jwks:
            mock_jwks.side_effect = Exception("JWKS unavailable")

            response = await client.post(
                "/api/v1/identities/validate",
                json={"token": "not.a.jwt"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert "error" in data

    @pytest.mark.asyncio
    async def test_validate_missing_token_returns_422(self, client: AsyncClient) -> None:
        """POST /validate without token field returns 422."""
        response = await client.post(
            "/api/v1/identities/validate",
            json={},
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
