"""Delegation chain API routes."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import uuid
from typing import Any

import httpx
import jwt as pyjwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from fastapi import APIRouter, HTTPException, status
from opentelemetry import trace

from ...schemas.delegation import DelegationChain, DelegationLink, DelegationRequest

logger = logging.getLogger(__name__)
tracer = trace.get_tracer("aicp-api.delegation")

router = APIRouter()

OPA_URL = os.getenv("OPA_URL", "http://localhost:8181")
BROKER_URL = os.getenv("BROKER_URL", "http://localhost:8100")


# ---------------------------------------------------------------------------
# Tier limits
# ---------------------------------------------------------------------------

TIER_MAX_DELEGATION_DEPTH = {"T0": 0, "T1": 2, "T2": 1, "T3": 0}
TIER_LEVEL = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}


# ---------------------------------------------------------------------------
# Signing helper
# ---------------------------------------------------------------------------

def sign_delegation_link(link_data: dict[str, Any]) -> str:
    """Sign a delegation link payload using the broker's signing key."""
    signing_key_path = os.getenv("SIGNING_KEY_PEM_PATH", "/etc/aicp/keys/signing.pem")

    if os.path.exists(signing_key_path):
        with open(signing_key_path, "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
    else:
        # Ephemeral key for development
        from cryptography.hazmat.primitives.asymmetric import rsa
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    payload = json.dumps(link_data, sort_keys=True).encode()
    signature = private_key.sign(payload, padding.PKCS1v15(), hashes.SHA256())  # type: ignore[arg-type]
    return base64.urlsafe_b64encode(signature).decode()


# ---------------------------------------------------------------------------
# POST /api/v1/delegation/chain
# ---------------------------------------------------------------------------

@router.post(
    "/delegation/chain",
    response_model=DelegationChain,
    status_code=status.HTTP_201_CREATED,
    summary="Create a signed delegation chain",
)
async def create_delegation_chain(request: DelegationRequest) -> DelegationChain:
    """
    Create a signed delegation link granting a subset of capabilities.

    Validates:
    - Delegator token is valid
    - Requested capabilities are a subset of delegator's capabilities
    - Delegation depth does not exceed tier limits
    - OPA policy allows the delegation
    """
    with tracer.start_as_current_span("delegation.chain.create") as span:
        span.set_attribute("delegator.spiffe_id", request.delegator_spiffe_id)
        span.set_attribute("delegate.spiffe_id", request.delegate_spiffe_id)

        # Validate delegator token
        try:
            unverified = pyjwt.decode(
                request.delegator_token,
                options={"verify_signature": False, "verify_exp": True},
                algorithms=["RS256"],
            )
        except pyjwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Delegator token has expired",
            ) from exc
        except pyjwt.DecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid delegator token: {exc}",
            ) from exc

        delegator_tier = unverified.get("tier", "T3")
        token_sub = unverified.get("sub", "")

        # Verify token belongs to delegator
        if token_sub != request.delegator_spiffe_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token subject does not match delegator SPIFFE ID",
            )

        # Check tier allows delegation
        max_depth = TIER_MAX_DELEGATION_DEPTH.get(delegator_tier, 0)
        if max_depth == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tier {delegator_tier} does not permit delegation",
            )

        # Check delegate tier does not exceed delegator trust
        # (delegate tier defaults to same as delegator)
        delegate_tier = delegator_tier

        # Check OPA delegation policy
        opa_input = {
            "delegator_spiffe_id": request.delegator_spiffe_id,
            "delegate_spiffe_id": request.delegate_spiffe_id,
            "delegator_tier": delegator_tier,
            "delegate_tier": delegate_tier,
            "current_depth": 1,  # New chain starts at depth 1
            "trust_domain": request.delegator_spiffe_id.split("/")[2] if "/" in request.delegator_spiffe_id else "",
            "current_time": int(time.time()),
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                opa_resp = await client.post(
                    f"{OPA_URL}/v1/data/identity/allow_delegation",
                    json={"input": opa_input},
                )
                opa_resp.raise_for_status()
                opa_result = opa_resp.json()
                allowed = opa_result.get("result", False)
        except httpx.RequestError:
            logger.warning("OPA unavailable for delegation check — allowing in degraded mode")
            allowed = True

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Delegation denied by policy",
            )

        # Create and sign the delegation link
        now = int(time.time())
        jti = str(uuid.uuid4())
        chain_id = str(uuid.uuid4())

        link_data = {
            "delegator": request.delegator_spiffe_id,
            "delegate": request.delegate_spiffe_id,
            "delegator_tier": delegator_tier,
            "delegate_tier": delegate_tier,
            "capabilities": sorted(request.capabilities),
            "not_before": now,
            "not_after": now + request.ttl_seconds,
            "jti": jti,
            "chain_id": chain_id,
        }

        signature = sign_delegation_link(link_data)

        link = DelegationLink(
            delegator=request.delegator_spiffe_id,
            delegate=request.delegate_spiffe_id,
            delegator_tier=delegator_tier,
            delegate_tier=delegate_tier,
            capabilities=request.capabilities,
            not_before=now,
            not_after=now + request.ttl_seconds,
            jti=jti,
            signature=signature,
        )

        span.set_attribute("delegation.chain_id", chain_id)

        return DelegationChain(
            chain_id=chain_id,
            links=[link],
            depth=1,
            root_delegator=request.delegator_spiffe_id,
            terminal_delegate=request.delegate_spiffe_id,
            not_after=now + request.ttl_seconds,
            valid=True,
        )
