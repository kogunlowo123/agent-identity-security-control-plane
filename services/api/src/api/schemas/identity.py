"""Pydantic schemas for identity API endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class IssueRequest(BaseModel):
    """Request to issue a new JWT + SVID for an agent."""

    spiffe_id: str = Field(
        ...,
        description="Full SPIFFE ID: spiffe://<trust-domain>/<path>",
        examples=["spiffe://agent-identity-security-control-plane/identity-auditor"],
    )
    tier: str = Field(
        ...,
        description="Trust tier: T0, T1, T2, T3",
        pattern="^T[0-3]$",
    )
    agent_id: str = Field(
        ...,
        description="Stable agent identifier",
        min_length=1,
        max_length=64,
    )
    requested_ttl: int | None = Field(
        None,
        ge=1,
        le=3600,
        description="Requested token TTL in seconds (capped by tier maximum)",
    )
    scope: str | None = Field(
        None,
        description="Requested scope string",
    )

    @field_validator("spiffe_id")
    @classmethod
    def validate_spiffe_scheme(cls, v: str) -> str:
        if not v.startswith("spiffe://"):
            raise ValueError("spiffe_id must start with 'spiffe://'")
        return v

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, v: str) -> str:
        if v not in {"T0", "T1", "T2", "T3"}:
            raise ValueError("tier must be one of T0, T1, T2, T3")
        return v


class IssueResponse(BaseModel):
    """Response from the identity issuance endpoint."""

    access_token: str = Field(..., description="Signed JWT access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token lifetime in seconds")
    jti: str = Field(..., description="JWT ID (unique token identifier)")
    tier: str = Field(..., description="Issued trust tier")
    sub: str = Field(..., description="Subject SPIFFE ID")
    issued_at: int = Field(..., description="Unix timestamp of issuance")
    scope: str | None = Field(None, description="Granted scope")


class ValidateRequest(BaseModel):
    """Request to validate a JWT token."""

    token: str = Field(..., description="JWT token to validate")
    required_tier: str | None = Field(
        None,
        description="If set, require token to be at least this tier",
        pattern="^T[0-3]$",
    )
    required_capability: str | None = Field(
        None,
        description="If set, require token to grant this capability",
    )


class AgentPrincipal(BaseModel):
    """Principal claims extracted from a validated JWT."""

    sub: str = Field(..., description="SPIFFE ID (subject)")
    jti: str = Field(..., description="JWT ID")
    tier: str = Field(..., description="Trust tier")
    agent_id: str = Field(..., description="Agent identifier")
    trust_domain: str = Field(..., description="SPIFFE trust domain")
    exp: int = Field(..., description="Expiry Unix timestamp")
    iat: int = Field(..., description="Issued-at Unix timestamp")
    iss: str = Field(..., description="Issuer")
    aud: str | list[str] = Field(..., description="Audience")


class ValidateResponse(BaseModel):
    """Response from the token validation endpoint."""

    valid: bool = Field(..., description="Whether the token is valid")
    principal: AgentPrincipal | None = Field(
        None,
        description="Principal claims (only present if valid=True)",
    )
    error: str | None = Field(None, description="Error message if invalid")


class IdentityRecord(BaseModel):
    """Full identity record from the registry."""

    id: str
    name: str
    description: str | None = None
    spiffe_id: str
    tier: str
    status: str
    capabilities: list[str] = Field(default_factory=list)
    authorized_tools: list[str] = Field(default_factory=list)
    max_delegation_depth: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
