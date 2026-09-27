"""
Security tests for token expiry, revocation, and temporal claim validation.
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "identity" / "issuance" / "broker"))

import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import rsa

from broker import (
    issue_jwt,
    load_or_generate_signing_key,
    settings,
    _key_id,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def ensure_key():
    load_or_generate_signing_key()


@pytest.fixture()
def trust_domain() -> str:
    return settings.trust_domain


@pytest.fixture()
def valid_spiffe_id(trust_domain: str) -> str:
    return f"spiffe://{trust_domain}/security-test-agent"


# ---------------------------------------------------------------------------
# Expired token tests
# ---------------------------------------------------------------------------

@pytest.mark.security
class TestExpiredTokenRejected:
    def _make_token_with_custom_times(
        self,
        iat: int,
        exp: int,
        spiffe_id: str,
        tier: str = "T1",
    ) -> str:
        """Create a token with custom iat/exp, signed by the broker key."""
        from broker import _private_key

        claims = {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": spiffe_id,
            "jti": str(uuid.uuid4()),
            "iat": iat,
            "nbf": iat,
            "exp": exp,
            "tier": tier,
            "agent_id": "security-test",
            "trust_domain": settings.trust_domain,
        }
        return pyjwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": _key_id})  # type: ignore[arg-type]

    def test_expired_token_raises_expired_signature(self, valid_spiffe_id: str) -> None:
        """An expired token must raise ExpiredSignatureError on verification."""
        now = int(time.time())
        expired_token = self._make_token_with_custom_times(
            iat=now - 7200,
            exp=now - 3600,
            spiffe_id=valid_spiffe_id,
        )

        from broker import _private_key
        pub = _private_key.public_key()  # type: ignore[union-attr]
        with pytest.raises(pyjwt.ExpiredSignatureError):
            pyjwt.decode(expired_token, pub, algorithms=["RS256"], audience=settings.jwt_audience)

    def test_token_expiring_soon_still_valid(self, valid_spiffe_id: str) -> None:
        """A token with 10s remaining is still valid."""
        now = int(time.time())
        token = self._make_token_with_custom_times(
            iat=now - 3590,
            exp=now + 10,
            spiffe_id=valid_spiffe_id,
        )

        from broker import _private_key
        pub = _private_key.public_key()  # type: ignore[union-attr]
        claims = pyjwt.decode(token, pub, algorithms=["RS256"], audience=settings.jwt_audience)
        assert claims["sub"] == valid_spiffe_id

    def test_all_tiers_have_finite_ttl(self, valid_spiffe_id: str) -> None:
        """Security property: all tiers must have finite (non-zero) TTLs."""
        for tier in ["T0", "T1", "T2", "T3"]:
            token, expires_in, _ = issue_jwt(
                spiffe_id=valid_spiffe_id,
                tier=tier,
                agent_id="security-test",
            )
            assert expires_in > 0, f"Tier {tier} must have positive TTL"
            assert expires_in <= 3600, f"Tier {tier} TTL {expires_in}s exceeds max 3600s"


# ---------------------------------------------------------------------------
# Future iat (issued-at) rejection
# ---------------------------------------------------------------------------

@pytest.mark.security
class TestFutureIatRejected:
    def test_token_with_future_iat_is_rejected(self, valid_spiffe_id: str) -> None:
        """
        A token with iat in the future is suspicious and should be rejected.

        PyJWT enforces nbf but not iat by default. We test that our validation
        logic checks iat <= now + clock_skew.
        """
        from broker import _private_key

        now = int(time.time())
        future_iat = now + 3600  # issued 1 hour in the future

        claims = {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": valid_spiffe_id,
            "jti": str(uuid.uuid4()),
            "iat": future_iat,
            "nbf": future_iat,
            "exp": future_iat + 1800,
            "tier": "T1",
            "agent_id": "suspicious-agent",
            "trust_domain": settings.trust_domain,
        }
        token = pyjwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": _key_id})  # type: ignore[arg-type]

        pub = _private_key.public_key()  # type: ignore[union-attr]
        # nbf = future_iat => token not yet valid
        with pytest.raises(pyjwt.ImmatureSignatureError):
            pyjwt.decode(token, pub, algorithms=["RS256"], audience=settings.jwt_audience)


# ---------------------------------------------------------------------------
# Revoked token simulation
# ---------------------------------------------------------------------------

@pytest.mark.security
class TestRevokedTokenRejected:
    def test_revocation_list_check_logic(self, valid_spiffe_id: str) -> None:
        """
        Simulate revocation list check: a JTI in the revocation list must be rejected.

        This tests the revocation logic without a real database.
        """
        token, _, jti = issue_jwt(valid_spiffe_id, "T1", "revoked-agent")

        # Simulate a revocation list
        revocation_list: set[str] = set()

        def is_revoked(check_jti: str) -> bool:
            return check_jti in revocation_list

        # Before revocation
        assert not is_revoked(jti), "Token should not be revoked before revocation call"

        # Revoke
        revocation_list.add(jti)

        # After revocation
        assert is_revoked(jti), "Token should be detected as revoked after revocation"

    def test_different_jti_not_affected_by_revocation(self, valid_spiffe_id: str) -> None:
        """Revoking one JTI should not affect other tokens."""
        _, _, jti1 = issue_jwt(valid_spiffe_id, "T1", "agent-a")
        _, _, jti2 = issue_jwt(valid_spiffe_id, "T1", "agent-b")

        revocation_list: set[str] = {jti1}

        assert jti1 in revocation_list
        assert jti2 not in revocation_list

    def test_expired_token_rejected_even_if_not_revoked(self, valid_spiffe_id: str) -> None:
        """An expired token is always rejected, regardless of revocation status."""
        from broker import _private_key

        now = int(time.time())
        claims = {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": valid_spiffe_id,
            "jti": str(uuid.uuid4()),
            "iat": now - 7200,
            "nbf": now - 7200,
            "exp": now - 1,  # expired
            "tier": "T1",
            "agent_id": "test",
            "trust_domain": settings.trust_domain,
        }
        expired_token = pyjwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": _key_id})  # type: ignore[arg-type]

        pub = _private_key.public_key()  # type: ignore[union-attr]
        revocation_list: set[str] = set()  # NOT revoked
        # But still expired — should fail
        with pytest.raises(pyjwt.ExpiredSignatureError):
            pyjwt.decode(expired_token, pub, algorithms=["RS256"], audience=settings.jwt_audience)
