"""Token-bucket rate limiting middleware per agent principal + tier."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import jwt as pyjwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Requests per minute per tier
TIER_RATE_LIMITS = {
    "T0": int(os.getenv("RATE_LIMIT_T0", "1000")),
    "T1": int(os.getenv("RATE_LIMIT_T1", "500")),
    "T2": int(os.getenv("RATE_LIMIT_T2", "100")),
    "T3": int(os.getenv("RATE_LIMIT_T3", "10")),
}

# In-memory token buckets (redis-backed in production)
_buckets: dict[str, dict[str, float]] = {}


def _get_bucket(principal_id: str, tier: str) -> dict[str, float]:
    key = f"{principal_id}:{tier}"
    if key not in _buckets:
        limit = TIER_RATE_LIMITS.get(tier, 10)
        _buckets[key] = {
            "tokens": float(limit),
            "last_refill": time.time(),
            "limit": float(limit),
        }
    return _buckets[key]


def _consume_token(principal_id: str, tier: str) -> bool:
    """Token bucket: return True if request is allowed, False if rate limited."""
    bucket = _get_bucket(principal_id, tier)
    now = time.time()

    # Refill based on elapsed time (per minute rate)
    elapsed = now - bucket["last_refill"]
    refill_rate = bucket["limit"] / 60.0  # tokens per second
    bucket["tokens"] = min(bucket["limit"], bucket["tokens"] + elapsed * refill_rate)
    bucket["last_refill"] = now

    if bucket["tokens"] >= 1.0:
        bucket["tokens"] -= 1.0
        return True
    return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-principal rate limiting based on JWT tier."""

    def __init__(self, app: Any, redis_url: str = "") -> None:
        super().__init__(app)
        self.redis_url = redis_url

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Skip rate limiting for health endpoints
        if request.url.path in {"/api/v1/health", "/api/v1/readiness", "/health"}:
            return await call_next(request)

        principal_id = "anonymous"
        tier = "T3"

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                claims = pyjwt.decode(
                    token,
                    options={"verify_signature": False, "verify_exp": False},
                    algorithms=["RS256"],
                )
                principal_id = claims.get("jti", claims.get("sub", "anonymous"))
                tier = claims.get("tier", "T3")
            except Exception:
                pass

        if not _consume_token(principal_id, tier):
            limit = TIER_RATE_LIMITS.get(tier, 10)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Tier {tier} limit: {limit} requests/minute",
                },
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Tier": tier,
                },
            )

        response = await call_next(request)
        return response
