"""JWT authentication middleware and dependency."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx
import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..schemas.identity import AgentPrincipal

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)

BROKER_URL = os.getenv("BROKER_URL", "http://localhost:8100")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "aicp-api")

_jwks_cache: dict[str, Any] | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 300.0


async def _get_jwks() -> dict[str, Any]:
    """Fetch and cache JWKS from the token broker."""
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache is None or (now - _jwks_fetched_at) > _JWKS_TTL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{BROKER_URL}/.well-known/jwks.json")
                resp.raise_for_status()
                _jwks_cache = resp.json()
                _jwks_fetched_at = now
        except Exception as exc:
            logger.error("Failed to fetch JWKS: %s", exc)
            if _jwks_cache is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication service unavailable",
                ) from exc
    return _jwks_cache  # type: ignore[return-value]


def _build_public_key(key_data: dict[str, Any]) -> Any:
    """Build a cryptography public key object from a JWK."""
    import base64
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

    def decode_b64url(s: str) -> int:
        padded = s + "=" * (4 - len(s) % 4)
        return int.from_bytes(base64.urlsafe_b64decode(padded), "big")

    n = decode_b64url(key_data["n"])
    e = decode_b64url(key_data["e"])
    return RSAPublicNumbers(e=e, n=n).public_key()


async def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> AgentPrincipal:
    """
    FastAPI dependency: extract and verify JWT, return AgentPrincipal.

    Raises HTTP 401 if no token or invalid token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        header = pyjwt.get_unverified_header(token)
        kid = header.get("kid", "")
    except pyjwt.DecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
        ) from exc

    jwks = await _get_jwks()

    matching_key = None
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid or not kid:
            matching_key = key_data
            break

    if matching_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token key not recognized",
        )

    pub_key = _build_public_key(matching_key)

    try:
        claims = pyjwt.decode(
            token,
            pub_key,
            algorithms=["RS256"],
            audience=JWT_AUDIENCE,
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        ) from exc
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc

    aud = claims.get("aud", "")
    return AgentPrincipal(
        sub=claims["sub"],
        jti=claims["jti"],
        tier=claims.get("tier", "T3"),
        agent_id=claims.get("agent_id", ""),
        trust_domain=claims.get("trust_domain", ""),
        exp=claims["exp"],
        iat=claims["iat"],
        iss=claims["iss"],
        aud=aud,
    )


class AuthMiddleware:
    """Optional: ASGI auth middleware (currently not applied globally)."""
    # Auth is handled per-route via get_current_principal dependency.
    pass
