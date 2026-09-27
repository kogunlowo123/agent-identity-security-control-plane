"""
Unit tests for OPA identity and delegation policies.

Tests run OPA via subprocess using the `opa eval` command.
Requires OPA binary to be installed (skips gracefully if not).
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import pytest

# Path to OPA policy files
POLICIES_DIR = Path(__file__).parent.parent.parent / "identity" / "authorization" / "opa" / "policies"
IDENTITY_REGO = POLICIES_DIR / "identity.rego"
DELEGATION_REGO = POLICIES_DIR / "delegation.rego"

TRUST_DOMAIN = "agent-identity-security-control-plane"


# ---------------------------------------------------------------------------
# OPA availability check
# ---------------------------------------------------------------------------

def opa_available() -> bool:
    """Return True if the 'opa' binary is accessible."""
    try:
        result = subprocess.run(["opa", "version"], capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


skip_without_opa = pytest.mark.skipif(
    not opa_available(),
    reason="OPA binary not found — install from https://openpolicyagent.org/docs/latest/#1-download-opa",
)


# ---------------------------------------------------------------------------
# OPA evaluation helper
# ---------------------------------------------------------------------------

def eval_opa(
    policy_file: Path,
    query: str,
    input_doc: dict,
    extra_files: list[Path] | None = None,
) -> dict:
    """
    Evaluate an OPA query against a policy file.

    Returns the parsed JSON result.
    """
    input_json = json.dumps(input_doc)
    cmd = ["opa", "eval", "--format", "json", "--data", str(policy_file)]

    if extra_files:
        for f in extra_files:
            cmd.extend(["--data", str(f)])

    cmd.extend(["--input", "/dev/stdin", query])

    result = subprocess.run(
        cmd,
        input=input_json,
        capture_output=True,
        text=True,
        timeout=10,
    )

    if result.returncode != 0:
        pytest.fail(f"OPA eval failed:\n{result.stderr}")

    output = json.loads(result.stdout)
    # result structure: {"result": [{"expressions": [{"value": ..., "text": ...}]}]}
    if not output.get("result"):
        return {}
    return output["result"][0]["expressions"][0]["value"]


# ---------------------------------------------------------------------------
# Identity Issuance Policy Tests
# ---------------------------------------------------------------------------

@skip_without_opa
class TestIdentityIssuancePolicy:
    def test_allow_issuance_valid_svid_t1(self) -> None:
        """Valid SPIFFE ID + valid tier + valid TTL should be allowed."""
        input_doc = {
            "subject_spiffe_id": f"spiffe://{TRUST_DOMAIN}/identity-auditor",
            "requested_tier": "T1",
            "requested_ttl": 1800,
            "trust_domain": TRUST_DOMAIN,
            "timestamp": int(time.time()),
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_issuance", input_doc)
        assert result is True, f"Expected allow_issuance=True, got: {result}"

    def test_allow_issuance_t0_max_ttl(self) -> None:
        input_doc = {
            "subject_spiffe_id": f"spiffe://{TRUST_DOMAIN}/token-inspector",
            "requested_tier": "T0",
            "requested_ttl": 3600,
            "trust_domain": TRUST_DOMAIN,
            "timestamp": int(time.time()),
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_issuance", input_doc)
        assert result is True

    def test_deny_issuance_invalid_spiffe_id(self) -> None:
        """Malformed SPIFFE ID should be denied."""
        input_doc = {
            "subject_spiffe_id": "not-a-spiffe-id",
            "requested_tier": "T1",
            "requested_ttl": 1800,
            "trust_domain": TRUST_DOMAIN,
            "timestamp": int(time.time()),
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_issuance", input_doc)
        assert result is False, f"Expected allow_issuance=False, got: {result}"

    def test_deny_issuance_wrong_trust_domain(self) -> None:
        """SPIFFE ID from wrong trust domain should be denied."""
        input_doc = {
            "subject_spiffe_id": "spiffe://evil.com/malicious-agent",
            "requested_tier": "T1",
            "requested_ttl": 1800,
            "trust_domain": TRUST_DOMAIN,
            "timestamp": int(time.time()),
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_issuance", input_doc)
        assert result is False

    def test_deny_issuance_ttl_exceeds_tier_max(self) -> None:
        """Requesting TTL above tier max should be denied."""
        input_doc = {
            "subject_spiffe_id": f"spiffe://{TRUST_DOMAIN}/test-agent",
            "requested_tier": "T3",
            "requested_ttl": 9999,  # T3 max is 300s
            "trust_domain": TRUST_DOMAIN,
            "timestamp": int(time.time()),
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_issuance", input_doc)
        assert result is False

    def test_deny_issuance_invalid_tier(self) -> None:
        """Unknown tier should be denied."""
        input_doc = {
            "subject_spiffe_id": f"spiffe://{TRUST_DOMAIN}/test-agent",
            "requested_tier": "T9",
            "requested_ttl": 300,
            "trust_domain": TRUST_DOMAIN,
            "timestamp": int(time.time()),
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_issuance", input_doc)
        assert result is False


# ---------------------------------------------------------------------------
# Delegation Policy Tests
# ---------------------------------------------------------------------------

@skip_without_opa
class TestDelegationPolicy:
    def test_delegation_depth_t1_allows_depth_1(self) -> None:
        """T1 allows delegation chain depth of 1 (< max 2)."""
        now = int(time.time())
        input_doc = {
            "delegator_spiffe_id": f"spiffe://{TRUST_DOMAIN}/identity-auditor",
            "delegate_spiffe_id": f"spiffe://{TRUST_DOMAIN}/sub-agent",
            "delegator_tier": "T1",
            "delegate_tier": "T1",
            "current_depth": 1,
            "trust_domain": TRUST_DOMAIN,
            "current_time": now,
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_delegation", input_doc)
        assert result is True

    def test_delegation_depth_t1_denies_at_max(self) -> None:
        """T1 should deny delegation when depth already equals max (2)."""
        now = int(time.time())
        input_doc = {
            "delegator_spiffe_id": f"spiffe://{TRUST_DOMAIN}/identity-auditor",
            "delegate_spiffe_id": f"spiffe://{TRUST_DOMAIN}/sub-agent",
            "delegator_tier": "T1",
            "delegate_tier": "T1",
            "current_depth": 2,  # T1 max is 2, so 2 >= 2 => deny
            "trust_domain": TRUST_DOMAIN,
            "current_time": now,
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_delegation", input_doc)
        assert result is False

    def test_t0_cannot_delegate(self) -> None:
        """T0 tier has max_delegation_depth=0, so delegation is always denied."""
        now = int(time.time())
        input_doc = {
            "delegator_spiffe_id": f"spiffe://{TRUST_DOMAIN}/token-inspector",
            "delegate_spiffe_id": f"spiffe://{TRUST_DOMAIN}/other-agent",
            "delegator_tier": "T0",
            "delegate_tier": "T1",
            "current_depth": 0,
            "trust_domain": TRUST_DOMAIN,
            "current_time": now,
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_delegation", input_doc)
        assert result is False

    def test_t3_cannot_delegate(self) -> None:
        """T3 tier has max_delegation_depth=0, so delegation is always denied."""
        now = int(time.time())
        input_doc = {
            "delegator_spiffe_id": f"spiffe://{TRUST_DOMAIN}/low-trust-agent",
            "delegate_spiffe_id": f"spiffe://{TRUST_DOMAIN}/another-agent",
            "delegator_tier": "T3",
            "delegate_tier": "T3",
            "current_depth": 0,
            "trust_domain": TRUST_DOMAIN,
            "current_time": now,
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_delegation", input_doc)
        assert result is False

    def test_delegate_cannot_have_higher_trust(self) -> None:
        """Delegate tier must not be higher trust than delegator."""
        now = int(time.time())
        input_doc = {
            "delegator_spiffe_id": f"spiffe://{TRUST_DOMAIN}/t1-agent",
            "delegate_spiffe_id": f"spiffe://{TRUST_DOMAIN}/t0-agent",
            "delegator_tier": "T1",
            "delegate_tier": "T0",  # higher trust than T1 — deny
            "current_depth": 1,
            "trust_domain": TRUST_DOMAIN,
            "current_time": now,
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_delegation", input_doc)
        assert result is False


# ---------------------------------------------------------------------------
# Tier TTL cap tests (policy evaluation)
# ---------------------------------------------------------------------------

@skip_without_opa
class TestTtlCapPolicy:
    def test_ttl_cap_t3_exactly_300_is_ok(self) -> None:
        input_doc = {
            "subject_spiffe_id": f"spiffe://{TRUST_DOMAIN}/t3-agent",
            "requested_tier": "T3",
            "requested_ttl": 300,
            "trust_domain": TRUST_DOMAIN,
            "timestamp": int(time.time()),
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_issuance", input_doc)
        assert result is True

    def test_ttl_cap_t3_301_is_denied(self) -> None:
        input_doc = {
            "subject_spiffe_id": f"spiffe://{TRUST_DOMAIN}/t3-agent",
            "requested_tier": "T3",
            "requested_ttl": 301,  # 1 second over T3 max
            "trust_domain": TRUST_DOMAIN,
            "timestamp": int(time.time()),
        }
        result = eval_opa(IDENTITY_REGO, "data.identity.allow_issuance", input_doc)
        assert result is False
