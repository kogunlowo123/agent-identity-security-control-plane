"""Tenant extraction middleware."""

from __future__ import annotations

import logging

import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Extract tenant context from JWT sub (SPIFFE trust domain) and inject
    into request.state for downstream use.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:  # type: ignore[override]
        tenant_id = "default"

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                claims = pyjwt.decode(
                    token,
                    options={"verify_signature": False, "verify_exp": False},
                    algorithms=["RS256"],
                )
                trust_domain = claims.get("trust_domain", "")
                if trust_domain:
                    tenant_id = trust_domain
            except Exception:
                pass

        request.state.tenant_id = tenant_id
        response = await call_next(request)
        response.headers["X-Tenant-ID"] = tenant_id
        return response


from typing import Any  # noqa: E402 — needed for type hint above
