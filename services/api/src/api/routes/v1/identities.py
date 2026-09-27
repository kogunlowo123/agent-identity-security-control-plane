"""
Identity API routes — issue, validate, and retrieve agent identities.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from typing import Annotated, Any

import httpx
import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from opentelemetry import trace

from ...schemas.identity import (
    AgentPrincipal,
    IdentityRecord,
    IssueRequest,
    IssueResponse,
    ValidateRequest,
    ValidateResponse,
)

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("aicp-api.identities")

router = APIRouter()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BROKER_URL = os.getenv("BROKER_URL", "http://localhost:8100")
OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "aicp-api")
JWT_ISSUER = os.getenv("JWT_ISSUER", "https://aicp.example.com")

TIER_TTLS: dict[str, int] = {
    "T0": 3600,
    "T1": 1800,
    "T2": 900,
    "T3": 300,
}


# ---------------------------------------------------------------------------
# Helper: emit CloudEvent
# ---------------------------------------------------------------------------

async def emit_cloud_event(event_type: str, data: dict[str, Any]) -> None:
    """Fire-and-forget CloudEvent emission via Pub/Sub / broker."""
    pubsub_topic = os.getenv(f"PUBSUB_TOPIC_{event_type.upper().replace('.', '_')}", "")
    if not pubsub_topic:
        return

    event = {
        "specversion": "1.0",
        "type": f"com.aicp.{event_type}",
        "source": "aicp-api",
        "id": str(uuid.uuid4()),
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "datacontenttype": "application/json",
        "data": data,
    }
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(
                pubsub_topic,
                json=event,
                headers={"Content-Type": "application/cloudevents+json"},
            )
    except Exception as exc:
        logger.warning("CloudEvent emission failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Helper: fetch JWKS from broker for token verification
# ---------------------------------------------------------------------------

_jwks_cache: dict[str, Any] | None = None
_jwks_fetched_at: float = 0.0
_JWKS_TTL = 300.0  # cache JWKS for 5 minutes


async def get_jwks() -> dict[str, Any]:
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if _jwks_cache is None or (now - _jwks_fetched_at) > _JWKS_TTL:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{BROKER_URL}/.well-known/jwks.json")
            resp.raise_for_status()
            _jwks_cache = resp.json()
            _jwks_fetched_at = now
    return _jwks_cache  # type: ignore[return-value]


def decode_token_from_jwks(token: str, jwks: dict[str, Any]) -> dict[str, Any]:
    """Decode and verify a JWT using the JWKS from the broker."""
    try:
        header = pyjwt.get_unverified_header(token)
        kid = header.get("kid", "")
    except pyjwt.DecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token format: {exc}",
        ) from exc

    # Find the matching key
    matching_key = None
    for key_data in jwks.get("keys", []):
        if key_data.get("kid") == kid or not kid:
            matching_key = key_data
            break

    if matching_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token key ID not found in JWKS",
        )

    # Reconstruct public key from JWK
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
    import base64

    def _decode_b64url(s: str) -> int:
        padded = s + "=" * (4 - len(s) % 4)
        return int.from_bytes(base64.urlsafe_b64decode(padded), "big")

    n = _decode_b64url(matching_key["n"])
    e = _decode_b64url(matching_key["e"])
    pub_numbers = RSAPublicNumbers(e=e, n=n)
    pub_key = pub_numbers.public_key()

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

    return claims


# ---------------------------------------------------------------------------
# POST /api/v1/identities/issue
# ---------------------------------------------------------------------------

@router.post(
    "/identities/issue",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue SVID + JWT for an agent principal",
)
async def issue_identity(
    request: IssueRequest,
    http_request: Request,
) -> IssueResponse:
    """
    Issue a signed JWT for the given SPIFFE ID after OPA policy evaluation.
    """
    with tracer.start_as_current_span("identities.issue") as span:
        span.set_attribute("spiffe.id", request.spiffe_id)
        span.set_attribute("requested.tier", request.tier)

        # Forward to broker for actual issuance
        issue_payload = {
            "spiffe_id": request.spiffe_id,
            "tier": request.tier,
            "agent_id": request.agent_id,
        }
        if request.requested_ttl:
            issue_payload["requested_ttl"] = request.requested_ttl

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{BROKER_URL}/token/issue",
                    json=issue_payload,
                )
                resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Broker returned error: %s", exc.response.text)
            if exc.response.status_code == 403:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Identity issuance denied by policy",
                ) from exc
            elif exc.response.status_code == 400:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=exc.response.json().get("detail", "Invalid request"),
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Broker service error",
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Broker service unavailable",
            ) from exc

        broker_response = resp.json()
        span.set_attribute("token.jti", broker_response.get("jti", ""))

        # Emit CloudEvent
        await emit_cloud_event(
            "identity.issued",
            {
                "spiffe_id": request.spiffe_id,
                "tier": request.tier,
                "agent_id": request.agent_id,
                "jti": broker_response.get("jti"),
            },
        )

        return IssueResponse(
            access_token=broker_response["access_token"],
            token_type=broker_response.get("token_type", "Bearer"),
            expires_in=broker_response["expires_in"],
            jti=broker_response["jti"],
            tier=broker_response["tier"],
            sub=broker_response["sub"],
            issued_at=int(time.time()),
            scope=broker_response.get("scope"),
        )


# ---------------------------------------------------------------------------
# POST /api/v1/identities/validate
# ---------------------------------------------------------------------------

@router.post(
    "/identities/validate",
    response_model=ValidateResponse,
    summary="Validate a JWT token and return principal claims",
)
async def validate_identity(request: ValidateRequest) -> ValidateResponse:
    """
    Validate a JWT token, verify signature via broker JWKS, return principal.
    """
    with tracer.start_as_current_span("identities.validate"):
        try:
            jwks = await get_jwks()
            claims = decode_token_from_jwks(request.token, jwks)
        except HTTPException as exc:
            return ValidateResponse(valid=False, error=str(exc.detail))

        # Check required_tier constraint
        if request.required_tier:
            tier_level = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}
            token_tier = claims.get("tier", "T3")
            required_level = tier_level.get(request.required_tier, 3)
            token_level = tier_level.get(token_tier, 3)
            if token_level > required_level:
                return ValidateResponse(
                    valid=False,
                    error=f"Token tier {token_tier} does not meet requirement {request.required_tier}",
                )

        aud = claims.get("aud", "")
        principal = AgentPrincipal(
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
        return ValidateResponse(valid=True, principal=principal)


# ---------------------------------------------------------------------------
# GET /api/v1/identities/{id}
# ---------------------------------------------------------------------------

@router.get(
    "/identities/{identity_id}",
    response_model=IdentityRecord,
    summary="Get an agent identity record by ID",
)
async def get_identity(identity_id: str) -> IdentityRecord:
    """
    Retrieve an agent identity record from the registry by agent ID or SPIFFE path.
    """
    with tracer.start_as_current_span("identities.get") as span:
        span.set_attribute("identity.id", identity_id)

        # Query identity registry from database
        db_url = os.getenv("DATABASE_URL", "postgresql://aicp_user:aicp_pass@localhost:5432/aicp_db")

        try:
            import psycopg2
            import psycopg2.extras

            conn = psycopg2.connect(db_url, connect_timeout=5)
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                    cur.execute(
                        """
                        SELECT id, name, description, spiffe_id, tier, status,
                               capabilities, authorized_tools, max_delegation_depth,
                               metadata, created_at, updated_at, revoked_at, revocation_reason
                        FROM agent_identities
                        WHERE id = %s OR spiffe_id LIKE %s
                        LIMIT 1
                        """,
                        (identity_id, f"%/{identity_id}"),
                    )
                    row = cur.fetchone()
            finally:
                conn.close()

            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Identity '{identity_id}' not found",
                )

            return IdentityRecord(**dict(row))

        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Database error retrieving identity %s: %s", identity_id, exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Identity registry unavailable",
            ) from exc
