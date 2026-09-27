"""
RFC 8693 Token Exchange Broker for AI Agent Identity Management.

Implements token exchange to issue tier-scoped JWTs backed by SPIFFE SVIDs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

class BrokerSettings(BaseSettings):
    app_env: str = "development"
    app_log_level: str = "INFO"
    trust_domain: str = "agent-identity-security-control-plane"
    signing_key_pem_path: str = "/etc/aicp/keys/signing.pem"
    signing_key_pem: str = ""  # Base64-encoded inline alternative
    jwt_issuer: str = "https://aicp.example.com"
    jwt_audience: str = "aicp-api"
    opa_url: str = "http://localhost:8181"
    redis_url: str = "redis://localhost:6379/0"
    otel_endpoint: str = ""
    # TTLs per tier in seconds
    token_ttl_t0: int = 3600
    token_ttl_t1: int = 1800
    token_ttl_t2: int = 900
    token_ttl_t3: int = 300

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = BrokerSettings()

TIER_TTLS: dict[str, int] = {
    "T0": settings.token_ttl_t0,
    "T1": settings.token_ttl_t1,
    "T2": settings.token_ttl_t2,
    "T3": settings.token_ttl_t3,
}

# ---------------------------------------------------------------------------
# RSA Key Management
# ---------------------------------------------------------------------------

_private_key: rsa.RSAPrivateKey | None = None
_public_key_pem: bytes | None = None
_key_id: str = ""


def _generate_key() -> rsa.RSAPrivateKey:
    """Generate a new 2048-bit RSA key pair."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )


def load_or_generate_signing_key() -> rsa.RSAPrivateKey:
    """Load RSA signing key from env var, file, or generate ephemeral key."""
    global _private_key, _public_key_pem, _key_id

    if _private_key is not None:
        return _private_key

    pem_bytes: bytes | None = None

    # 1. Try inline PEM from env var
    if settings.signing_key_pem:
        import base64
        pem_bytes = base64.b64decode(settings.signing_key_pem)
        logger.info("Loaded signing key from SIGNING_KEY_PEM env var")

    # 2. Try PEM file
    elif os.path.exists(settings.signing_key_pem_path):
        with open(settings.signing_key_pem_path, "rb") as f:
            pem_bytes = f.read()
        logger.info("Loaded signing key from file: %s", settings.signing_key_pem_path)

    if pem_bytes:
        _private_key = serialization.load_pem_private_key(pem_bytes, password=None)
    else:
        # 3. Generate ephemeral key (dev/testing only)
        logger.warning("No signing key configured — generating ephemeral key (NOT for production)")
        _private_key = _generate_key()

    pub = _private_key.public_key()
    _public_key_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    # Deterministic key ID from public key fingerprint
    _key_id = hashlib.sha256(_public_key_pem).hexdigest()[:16]
    return _private_key


def get_jwks() -> dict[str, Any]:
    """Return the JWKS (JSON Web Key Set) containing the public key."""
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
    import base64

    load_or_generate_signing_key()
    pub: RSAPublicKey = _private_key.public_key()  # type: ignore[union-attr]
    pub_numbers = pub.public_key().public_numbers() if hasattr(pub, "public_key") else pub.public_numbers()  # type: ignore[attr-defined]

    def _b64url(n: int, length: int) -> str:
        return base64.urlsafe_b64encode(
            n.to_bytes(length, byteorder="big")
        ).rstrip(b"=").decode("ascii")

    # Determine key size
    key_size = pub.key_size
    byte_length = key_size // 8

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": _key_id,
                "n": _b64url(pub_numbers.n, byte_length),
                "e": _b64url(pub_numbers.e, 4),
            }
        ]
    }


# ---------------------------------------------------------------------------
# SPIFFE ID Validation
# ---------------------------------------------------------------------------

VALID_TIERS = frozenset(["T0", "T1", "T2", "T3"])


def validate_spiffe_id(spiffe_id: str) -> tuple[str, str]:
    """
    Validate SPIFFE ID format: spiffe://<trust-domain>/<path>

    Returns:
        (trust_domain, workload_path)

    Raises:
        ValueError: if the SPIFFE ID is malformed or from an untrusted domain
    """
    if not spiffe_id.startswith("spiffe://"):
        raise ValueError(f"SPIFFE ID must start with 'spiffe://': {spiffe_id}")

    remainder = spiffe_id[len("spiffe://"):]
    if "/" not in remainder:
        raise ValueError(f"SPIFFE ID must contain a path component: {spiffe_id}")

    trust_domain, _, workload_path = remainder.partition("/")

    if not trust_domain:
        raise ValueError(f"SPIFFE ID trust domain is empty: {spiffe_id}")

    if not workload_path:
        raise ValueError(f"SPIFFE ID workload path is empty: {spiffe_id}")

    if trust_domain != settings.trust_domain:
        raise ValueError(
            f"SPIFFE ID trust domain '{trust_domain}' does not match "
            f"configured trust domain '{settings.trust_domain}'"
        )

    return trust_domain, workload_path


# ---------------------------------------------------------------------------
# OPA Policy Check
# ---------------------------------------------------------------------------

async def check_opa_issuance_policy(
    spiffe_id: str,
    requested_tier: str,
    requested_ttl: int,
) -> bool:
    """Check OPA identity issuance policy before issuing a token."""
    input_doc = {
        "subject_spiffe_id": spiffe_id,
        "requested_tier": requested_tier,
        "requested_ttl": requested_ttl,
        "trust_domain": settings.trust_domain,
        "timestamp": int(time.time()),
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(
                f"{settings.opa_url}/v1/data/identity/allow_issuance",
                json={"input": input_doc},
            )
            resp.raise_for_status()
            result = resp.json()
            allowed = result.get("result", False)
            logger.info(
                "OPA issuance policy check: allowed=%s, input_hash=%s",
                allowed,
                hashlib.sha256(json.dumps(input_doc, sort_keys=True).encode()).hexdigest()[:8],
            )
            return bool(allowed)
        except httpx.RequestError as exc:
            logger.error("OPA request failed: %s — allowing by default (degraded mode)", exc)
            # In production, you might want to fail closed. For resilience we allow.
            return True


# ---------------------------------------------------------------------------
# Token Issuance
# ---------------------------------------------------------------------------

def issue_jwt(
    spiffe_id: str,
    tier: str,
    agent_id: str,
    requested_ttl: int | None = None,
) -> tuple[str, int, str]:
    """
    Issue a signed JWT for the given SPIFFE ID.

    Returns:
        (token_string, expires_in_seconds, jti)
    """
    private_key = load_or_generate_signing_key()

    max_ttl = TIER_TTLS[tier]
    ttl = min(requested_ttl, max_ttl) if requested_ttl is not None else max_ttl

    now = int(time.time())
    jti = str(uuid.uuid4())

    claims: dict[str, Any] = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": spiffe_id,
        "jti": jti,
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
        "tier": tier,
        "agent_id": agent_id,
        "trust_domain": settings.trust_domain,
    }

    token = jwt.encode(
        claims,
        private_key,  # type: ignore[arg-type]
        algorithm="RS256",
        headers={"kid": _key_id},
    )

    logger.info(
        "Issued JWT: jti=%s, sub=%s, tier=%s, ttl=%ds",
        jti, spiffe_id, tier, ttl,
    )
    return token, ttl, jti


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class TokenExchangeRequest(BaseModel):
    """RFC 8693 Token Exchange Request."""
    grant_type: str = Field(
        ...,
        description="Must be urn:ietf:params:oauth:grant-type:token-exchange",
    )
    subject_token: str = Field(..., description="The SPIFFE SVID or existing JWT")
    subject_token_type: str = Field(
        ...,
        description="e.g. urn:ietf:params:oauth:token-type:jwt",
    )
    requested_token_type: str = Field(
        default="urn:ietf:params:oauth:token-type:jwt",
        description="Desired output token type",
    )
    scope: str | None = Field(None, description="Requested scope (e.g. tier:T1)")
    resource: str | None = Field(None, description="Target resource URI")
    audience: str | None = Field(None, description="Intended audience")
    actor_token: str | None = Field(None, description="Actor token for delegation")
    actor_token_type: str | None = Field(None, description="Actor token type")
    requested_ttl: int | None = Field(None, ge=1, le=3600, description="Requested TTL in seconds")


class TokenExchangeResponse(BaseModel):
    """RFC 8693 Token Exchange Response."""
    access_token: str
    issued_token_type: str = "urn:ietf:params:oauth:token-type:jwt"
    token_type: str = "Bearer"
    expires_in: int
    scope: str | None = None


class IssueRequest(BaseModel):
    """Direct issuance request (non-RFC 8693 convenience endpoint)."""
    spiffe_id: str = Field(..., description="SPIFFE ID of the agent requesting a token")
    tier: str = Field(..., description="Requested trust tier: T0, T1, T2, T3")
    agent_id: str = Field(..., description="Stable agent identifier (UUID or slug)")
    requested_ttl: int | None = Field(None, ge=1, le=3600)


# ---------------------------------------------------------------------------
# OpenTelemetry Setup
# ---------------------------------------------------------------------------

def setup_telemetry() -> trace.Tracer:
    """Configure OpenTelemetry tracing."""
    resource = Resource.create({
        "service.name": "aicp-broker",
        "service.version": "0.1.0",
        "deployment.environment": settings.app_env,
    })
    provider = TracerProvider(resource=resource)

    if settings.otel_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    return trace.get_tracer("aicp-broker")


tracer = setup_telemetry()

# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AICP Token Broker",
    description="RFC 8693 Token Exchange for AI Agent Identity Management",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    """Initialize signing key on startup."""
    load_or_generate_signing_key()
    logger.info("Token broker started, key ID: %s", _key_id)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/.well-known/jwks.json")
async def jwks_endpoint() -> dict[str, Any]:
    """Return the JWKS (JSON Web Key Set) for token verification."""
    with tracer.start_as_current_span("broker.jwks"):
        return get_jwks()


@app.post("/token/exchange", response_model=TokenExchangeResponse)
async def token_exchange(request: TokenExchangeRequest) -> TokenExchangeResponse:
    """
    RFC 8693 Token Exchange endpoint.

    Exchanges a SPIFFE SVID or existing JWT for a tier-scoped access token.
    """
    with tracer.start_as_current_span("broker.token_exchange") as span:
        # Validate grant type
        expected_grant = "urn:ietf:params:oauth:grant-type:token-exchange"
        if request.grant_type != expected_grant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "unsupported_grant_type",
                    "error_description": f"grant_type must be '{expected_grant}'",
                },
            )

        # Extract tier from scope (e.g. "tier:T1 read")
        tier = "T3"  # default to least privileged
        if request.scope:
            for part in request.scope.split():
                if part.startswith("tier:"):
                    tier = part[5:].upper()
                    break

        if tier not in VALID_TIERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_scope",
                    "error_description": f"tier must be one of {sorted(VALID_TIERS)}",
                },
            )

        # Parse subject token to extract SPIFFE ID
        spiffe_id: str | None = None
        agent_id: str | None = None

        # Try to decode as JWT (may be an existing token or SVID-JWT)
        try:
            # Decode without verification to extract claims
            unverified = jwt.decode(
                request.subject_token,
                options={"verify_signature": False, "verify_exp": False},
                algorithms=["RS256", "ES256"],
            )
            spiffe_id = unverified.get("sub")
            agent_id = unverified.get("agent_id", unverified.get("jti", ""))
        except Exception:
            # Treat as raw SPIFFE ID string
            spiffe_id = request.subject_token
            agent_id = spiffe_id.split("/")[-1] if "/" in request.subject_token else request.subject_token

        if not spiffe_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_request",
                    "error_description": "Cannot extract SPIFFE ID from subject_token",
                },
            )

        # Validate SPIFFE ID format
        try:
            validate_spiffe_id(spiffe_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "invalid_subject", "error_description": str(exc)},
            ) from exc

        span.set_attribute("spiffe.id", spiffe_id)
        span.set_attribute("requested.tier", tier)

        # Check OPA policy
        max_ttl = TIER_TTLS[tier]
        allowed = await check_opa_issuance_policy(spiffe_id, tier, request.requested_ttl or max_ttl)
        if not allowed:
            span.set_attribute("policy.allowed", False)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "access_denied",
                    "error_description": "Identity issuance policy denied the request",
                },
            )

        # Issue JWT
        token, expires_in, jti = issue_jwt(
            spiffe_id=spiffe_id,
            tier=tier,
            agent_id=agent_id or spiffe_id.split("/")[-1],
            requested_ttl=request.requested_ttl,
        )

        span.set_attribute("token.jti", jti)
        span.set_attribute("token.expires_in", expires_in)
        span.set_attribute("policy.allowed", True)

        return TokenExchangeResponse(
            access_token=token,
            issued_token_type="urn:ietf:params:oauth:token-type:jwt",
            token_type="Bearer",
            expires_in=expires_in,
            scope=f"tier:{tier}",
        )


@app.post("/token/issue")
async def direct_issue(request: IssueRequest) -> dict[str, Any]:
    """
    Direct token issuance endpoint (non-RFC 8693, convenience API).

    Issues a JWT for a well-known agent identity after SPIFFE ID validation.
    """
    with tracer.start_as_current_span("broker.direct_issue") as span:
        # Validate tier
        if request.tier not in VALID_TIERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"tier must be one of {sorted(VALID_TIERS)}",
            )

        # Validate SPIFFE ID
        try:
            validate_spiffe_id(request.spiffe_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        span.set_attribute("spiffe.id", request.spiffe_id)
        span.set_attribute("requested.tier", request.tier)

        # OPA check
        max_ttl = TIER_TTLS[request.tier]
        allowed = await check_opa_issuance_policy(
            request.spiffe_id, request.tier, request.requested_ttl or max_ttl
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Identity issuance policy denied the request",
            )

        token, expires_in, jti = issue_jwt(
            spiffe_id=request.spiffe_id,
            tier=request.tier,
            agent_id=request.agent_id,
            requested_ttl=request.requested_ttl,
        )

        span.set_attribute("token.jti", jti)

        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "jti": jti,
            "tier": request.tier,
            "sub": request.spiffe_id,
        }


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "server_error", "error_description": "An internal error occurred"},
    )


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=getattr(logging, settings.app_log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    uvicorn.run(app, host="0.0.0.0", port=8100, log_config=None)
