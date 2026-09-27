"""
Unit tests for identity issuance: JWT generation, TTL enforcement, SPIFFE ID validation.

All tests are self-contained and require no external services.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import pytest

# Add broker to path so we can import its functions directly
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "identity" / "issuance" / "broker"))

import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa

# Import functions under test
from broker import (
    TIER_TTLS,
    VALID_TIERS,
    issue_jwt,
    load_or_generate_signing_key,
    validate_spiffe_id,
    settings,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def ensure_signing_key():
    """Ensure a signing key is loaded before each test."""
    load_or_generate_signing_key()


@pytest.fixture()
def trust_domain() -> str:
    return settings.trust_domain


@pytest.fixture()
def valid_spiffe_id(trust_domain: str) -> str:
    return f"spiffe://{trust_domain}/identity-auditor"


@pytest.fixture()
def valid_agent_id() -> str:
    return f"agent-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# validate_spiffe_id tests
# ---------------------------------------------------------------------------

class TestValidateSpiffeId:
    def test_valid_spiffe_id_returns_components(self, trust_domain: str, valid_spiffe_id: str) -> None:
        td, path = validate_spiffe_id(valid_spiffe_id)
        assert td == trust_domain
        assert path == "identity-auditor"

    def test_missing_scheme_raises(self, trust_domain: str) -> None:
        with pytest.raises(ValueError, match="must start with 'spiffe://'"):
            validate_spiffe_id(f"{trust_domain}/identity-auditor")

    def test_empty_trust_domain_raises(self) -> None:
        with pytest.raises(ValueError):
            validate_spiffe_id("spiffe:///identity-auditor")

    def test_missing_path_raises(self, trust_domain: str) -> None:
        with pytest.raises(ValueError, match="workload path"):
            validate_spiffe_id(f"spiffe://{trust_domain}/")

    def test_wrong_trust_domain_raises(self, trust_domain: str) -> None:
        with pytest.raises(ValueError, match="does not match"):
            validate_spiffe_id("spiffe://evil-domain/malicious-agent")

    def test_nested_path_is_valid(self, trust_domain: str) -> None:
        td, path = validate_spiffe_id(f"spiffe://{trust_domain}/agents/group/worker")
        assert td == trust_domain
        assert path == "agents/group/worker"


# ---------------------------------------------------------------------------
# issue_jwt tests
# ---------------------------------------------------------------------------

class TestIssueJwt:
    def test_issue_jwt_returns_string(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        token, expires_in, jti = issue_jwt(
            spiffe_id=valid_spiffe_id,
            tier="T1",
            agent_id=valid_agent_id,
        )
        assert isinstance(token, str)
        assert len(token) > 0

    def test_jwt_contains_required_claims(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        token, _, _ = issue_jwt(
            spiffe_id=valid_spiffe_id,
            tier="T1",
            agent_id=valid_agent_id,
        )
        from broker import _private_key
        pub_key = _private_key.public_key()  # type: ignore[union-attr]
        claims = pyjwt.decode(token, pub_key, algorithms=["RS256"], audience=settings.jwt_audience)

        assert claims["sub"] == valid_spiffe_id
        assert claims["tier"] == "T1"
        assert claims["agent_id"] == valid_agent_id
        assert "jti" in claims
        assert "iat" in claims
        assert "exp" in claims
        assert "iss" in claims
        assert "aud" in claims

    def test_jti_is_unique_per_issuance(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        _, _, jti1 = issue_jwt(valid_spiffe_id, "T1", valid_agent_id)
        _, _, jti2 = issue_jwt(valid_spiffe_id, "T1", valid_agent_id)
        assert jti1 != jti2

    def test_jwt_signed_with_rs256(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        token, _, _ = issue_jwt(valid_spiffe_id, "T0", valid_agent_id)
        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "RS256"

    def test_jwt_has_kid_in_header(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        token, _, _ = issue_jwt(valid_spiffe_id, "T0", valid_agent_id)
        header = pyjwt.get_unverified_header(token)
        assert "kid" in header
        assert len(header["kid"]) > 0


# ---------------------------------------------------------------------------
# TTL per tier
# ---------------------------------------------------------------------------

class TestTierTtl:
    def _decode_exp(self, token: str) -> int:
        claims = pyjwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=["RS256"],
        )
        return int(claims["exp"]) - int(claims["iat"])

    def test_t0_tier_ttl_is_3600s(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        token, expires_in, _ = issue_jwt(valid_spiffe_id, "T0", valid_agent_id)
        assert expires_in == 3600
        assert self._decode_exp(token) == 3600

    def test_t1_tier_ttl_is_1800s(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        token, expires_in, _ = issue_jwt(valid_spiffe_id, "T1", valid_agent_id)
        assert expires_in == 1800
        assert self._decode_exp(token) == 1800

    def test_t2_tier_ttl_is_900s(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        token, expires_in, _ = issue_jwt(valid_spiffe_id, "T2", valid_agent_id)
        assert expires_in == 900
        assert self._decode_exp(token) == 900

    def test_t3_tier_ttl_is_300s(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        token, expires_in, _ = issue_jwt(valid_spiffe_id, "T3", valid_agent_id)
        assert expires_in == 300
        assert self._decode_exp(token) == 300

    def test_requested_ttl_capped_at_tier_max(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        # T3 max is 300s — requesting 9999 should be capped
        token, expires_in, _ = issue_jwt(
            valid_spiffe_id, "T3", valid_agent_id, requested_ttl=9999
        )
        assert expires_in == 300
        assert self._decode_exp(token) == 300

    def test_requested_ttl_below_max_honored(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        # T0 max is 3600s — requesting 120 should be honored
        token, expires_in, _ = issue_jwt(
            valid_spiffe_id, "T0", valid_agent_id, requested_ttl=120
        )
        assert expires_in == 120
        assert self._decode_exp(token) == 120

    def test_all_tiers_have_configured_ttl(self) -> None:
        assert set(TIER_TTLS.keys()) == {"T0", "T1", "T2", "T3"}
        assert TIER_TTLS["T0"] == 3600
        assert TIER_TTLS["T1"] == 1800
        assert TIER_TTLS["T2"] == 900
        assert TIER_TTLS["T3"] == 300


# ---------------------------------------------------------------------------
# Invalid tier handling
# ---------------------------------------------------------------------------

class TestInvalidTier:
    def test_invalid_tier_key_error(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        with pytest.raises(KeyError):
            issue_jwt(valid_spiffe_id, "T9", valid_agent_id)

    def test_valid_tiers_set_is_correct(self) -> None:
        assert VALID_TIERS == frozenset({"T0", "T1", "T2", "T3"})


# ---------------------------------------------------------------------------
# Token signature verification
# ---------------------------------------------------------------------------

class TestTokenSignatureVerification:
    def test_valid_token_verifies_with_public_key(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        from broker import _private_key
        token, _, _ = issue_jwt(valid_spiffe_id, "T1", valid_agent_id)
        pub_key = _private_key.public_key()  # type: ignore[union-attr]
        claims = pyjwt.decode(token, pub_key, algorithms=["RS256"], audience=settings.jwt_audience)
        assert claims["sub"] == valid_spiffe_id

    def test_tampered_token_fails_verification(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        from broker import _private_key
        token, _, _ = issue_jwt(valid_spiffe_id, "T1", valid_agent_id)
        # Tamper: flip last char
        tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
        pub_key = _private_key.public_key()  # type: ignore[union-attr]
        with pytest.raises(pyjwt.InvalidSignatureError):
            pyjwt.decode(tampered, pub_key, algorithms=["RS256"], audience=settings.jwt_audience)

    def test_wrong_key_fails_verification(self, valid_spiffe_id: str, valid_agent_id: str) -> None:
        token, _, _ = issue_jwt(valid_spiffe_id, "T1", valid_agent_id)
        # Generate a different key for verification
        wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        wrong_pub = wrong_key.public_key()
        with pytest.raises(pyjwt.InvalidSignatureError):
            pyjwt.decode(token, wrong_pub, algorithms=["RS256"], audience=settings.jwt_audience)
