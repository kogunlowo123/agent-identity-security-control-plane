"""Pydantic schemas for delegation chain API endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class DelegationRequest(BaseModel):
    """Request to create a signed delegation link."""

    delegator_spiffe_id: str = Field(
        ...,
        description="SPIFFE ID of the delegating principal",
    )
    delegate_spiffe_id: str = Field(
        ...,
        description="SPIFFE ID of the agent receiving delegated authority",
    )
    capabilities: list[str] = Field(
        ...,
        description="Capabilities being delegated (must be subset of delegator's)",
        min_length=1,
    )
    ttl_seconds: int = Field(
        ...,
        ge=60,
        le=3600,
        description="Delegation chain TTL in seconds",
    )
    delegator_token: str = Field(
        ...,
        description="Delegator's current JWT (for verification)",
    )

    @field_validator("delegator_spiffe_id", "delegate_spiffe_id")
    @classmethod
    def validate_spiffe_scheme(cls, v: str) -> str:
        if not v.startswith("spiffe://"):
            raise ValueError("SPIFFE ID must start with 'spiffe://'")
        return v

    @field_validator("capabilities")
    @classmethod
    def validate_capabilities_not_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one capability must be delegated")
        return v


class DelegationLink(BaseModel):
    """A single signed link in a delegation chain."""

    delegator: str = Field(..., description="Delegator SPIFFE ID")
    delegate: str = Field(..., description="Delegate SPIFFE ID")
    delegator_tier: str = Field(..., description="Delegator trust tier")
    delegate_tier: str = Field(..., description="Delegate trust tier")
    capabilities: list[str] = Field(..., description="Delegated capabilities")
    not_before: int = Field(..., description="Unix timestamp — valid from")
    not_after: int = Field(..., description="Unix timestamp — valid until")
    jti: str = Field(..., description="Unique delegation link ID")
    signature: str = Field(..., description="RS256 signature over the link")


class DelegationChain(BaseModel):
    """A complete delegation chain response."""

    chain_id: str = Field(..., description="Unique chain identifier")
    links: list[DelegationLink] = Field(..., description="Ordered delegation links")
    depth: int = Field(..., description="Chain depth (number of links)")
    root_delegator: str = Field(..., description="Original delegating principal")
    terminal_delegate: str = Field(..., description="Final receiving agent")
    not_after: int = Field(..., description="Earliest expiry across all links")
    valid: bool = Field(..., description="Whether the chain is currently valid")
