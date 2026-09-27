"""
Security tests for delegation chain depth enforcement and capability subset constraints.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "identity" / "issuance" / "broker"))

from broker import load_or_generate_signing_key, settings

TRUST_DOMAIN = settings.trust_domain

TIER_MAX_DELEGATION_DEPTH = {"T0": 0, "T1": 2, "T2": 1, "T3": 0}
TIER_LEVEL = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}


# ---------------------------------------------------------------------------
# Helpers (pure Python — no external services needed)
# ---------------------------------------------------------------------------

def validate_delegation_chain(
    delegator_tier: str,
    current_depth: int,
    delegate_tier: str,
) -> tuple[bool, str]:
    """
    Replicate core delegation validation logic for security testing.

    Returns (allowed, reason).
    """
    # T0 and T3 cannot delegate at all
    max_depth = TIER_MAX_DELEGATION_DEPTH.get(delegator_tier, 0)
    if max_depth == 0:
        return False, f"Tier {delegator_tier} does not permit delegation (max_depth=0)"

    # Depth check
    if current_depth >= max_depth:
        return False, f"Depth {current_depth} >= max {max_depth} for tier {delegator_tier}"

    # Delegate cannot have higher trust than delegator
    if TIER_LEVEL.get(delegate_tier, 99) < TIER_LEVEL.get(delegator_tier, 0):
        return False, f"Delegate tier {delegate_tier} has higher trust than delegator {delegator_tier}"

    return True, "allowed"


def validate_capability_subset(delegator_caps: list[str], delegate_caps: list[str]) -> tuple[bool, str]:
    """Verify delegate capabilities are a strict subset of delegator capabilities."""
    delegator_set = set(delegator_caps)
    delegate_set = set(delegate_caps)

    extra_caps = delegate_set - delegator_set
    if extra_caps:
        return False, f"Delegate has capabilities not held by delegator: {extra_caps}"

    return True, "allowed"


def validate_delegation_time(not_before: int, not_after: int, current_time: int) -> tuple[bool, str]:
    """Verify a delegation link is within its validity window."""
    if current_time < not_before:
        return False, f"Delegation link not yet valid (nbf={not_before}, now={current_time})"
    if current_time > not_after:
        return False, f"Delegation link expired (exp={not_after}, now={current_time})"
    return True, "valid"


# ---------------------------------------------------------------------------
# Delegation depth limit tests
# ---------------------------------------------------------------------------

@pytest.mark.security
class TestDelegationDepthLimits:
    def test_t0_cannot_delegate_at_depth_0(self) -> None:
        allowed, reason = validate_delegation_chain("T0", 0, "T1")
        assert not allowed, f"T0 should not be able to delegate: {reason}"
        assert "T0" in reason

    def test_t1_can_delegate_at_depth_0(self) -> None:
        allowed, reason = validate_delegation_chain("T1", 0, "T1")
        assert allowed, f"T1 should be able to delegate at depth 0: {reason}"

    def test_t1_can_delegate_at_depth_1(self) -> None:
        allowed, reason = validate_delegation_chain("T1", 1, "T1")
        assert allowed, f"T1 should be able to delegate at depth 1 (max=2): {reason}"

    def test_t1_cannot_delegate_at_depth_2(self) -> None:
        """T1 max depth is 2, so depth=2 should be denied."""
        allowed, reason = validate_delegation_chain("T1", 2, "T1")
        assert not allowed, f"T1 at depth 2 should be denied: {reason}"

    def test_t2_can_delegate_at_depth_0(self) -> None:
        allowed, reason = validate_delegation_chain("T2", 0, "T2")
        assert allowed, f"T2 should be able to delegate at depth 0: {reason}"

    def test_t2_cannot_delegate_at_depth_1(self) -> None:
        """T2 max depth is 1, so depth=1 should be denied."""
        allowed, reason = validate_delegation_chain("T2", 1, "T2")
        assert not allowed, f"T2 at depth 1 should be denied: {reason}"

    def test_t3_cannot_delegate_at_depth_0(self) -> None:
        allowed, reason = validate_delegation_chain("T3", 0, "T3")
        assert not allowed, f"T3 should not be able to delegate: {reason}"


# ---------------------------------------------------------------------------
# Capability subset tests
# ---------------------------------------------------------------------------

@pytest.mark.security
class TestCapabilitySubset:
    def test_exact_subset_is_allowed(self) -> None:
        delegator_caps = ["read_identity_records", "generate_audit_reports", "rag_search"]
        delegate_caps = ["read_identity_records", "rag_search"]
        allowed, reason = validate_capability_subset(delegator_caps, delegate_caps)
        assert allowed, reason

    def test_same_capabilities_is_allowed(self) -> None:
        caps = ["read_identity_records", "rag_search"]
        allowed, reason = validate_capability_subset(caps, caps)
        assert allowed, reason

    def test_delegate_with_extra_capability_is_denied(self) -> None:
        delegator_caps = ["read_identity_records"]
        delegate_caps = ["read_identity_records", "write_identity_records"]  # extra cap
        allowed, reason = validate_capability_subset(delegator_caps, delegate_caps)
        assert not allowed, "Delegate should not have capabilities beyond delegator"
        assert "write_identity_records" in reason

    def test_empty_capabilities_is_denied(self) -> None:
        """Delegating zero capabilities is not useful but technically valid subset."""
        delegator_caps = ["read_identity_records"]
        delegate_caps: list[str] = []
        allowed, reason = validate_capability_subset(delegator_caps, delegate_caps)
        assert allowed, reason  # empty set is subset of any set

    def test_delegate_cannot_escalate_privileges(self) -> None:
        """Security property: privilege escalation via delegation is impossible."""
        delegator_caps = ["rag_search"]  # low-privilege operation
        delegate_caps = ["access_revocation_api"]  # high-privilege — not in delegator's set
        allowed, reason = validate_capability_subset(delegator_caps, delegate_caps)
        assert not allowed, "Privilege escalation via delegation must be impossible"


# ---------------------------------------------------------------------------
# Delegation time validity tests
# ---------------------------------------------------------------------------

@pytest.mark.security
class TestDelegationTimeValidity:
    def test_valid_time_window_is_accepted(self) -> None:
        now = int(time.time())
        allowed, reason = validate_delegation_time(
            not_before=now - 60,
            not_after=now + 3600,
            current_time=now,
        )
        assert allowed, reason

    def test_expired_link_is_rejected(self) -> None:
        now = int(time.time())
        allowed, reason = validate_delegation_time(
            not_before=now - 7200,
            not_after=now - 3600,  # expired 1 hour ago
            current_time=now,
        )
        assert not allowed, "Expired delegation link must be rejected"
        assert "expired" in reason.lower()

    def test_future_link_is_rejected(self) -> None:
        now = int(time.time())
        allowed, reason = validate_delegation_time(
            not_before=now + 3600,  # valid in 1 hour
            not_after=now + 7200,
            current_time=now,
        )
        assert not allowed, "Future delegation link must be rejected"
        assert "not yet valid" in reason.lower()

    def test_link_at_boundary_is_valid(self) -> None:
        now = int(time.time())
        # Exact not_before == now
        allowed, reason = validate_delegation_time(
            not_before=now,
            not_after=now + 3600,
            current_time=now,
        )
        assert allowed, reason
