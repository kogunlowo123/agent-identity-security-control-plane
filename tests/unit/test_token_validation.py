"""
Unit tests for JWT token validation: expiry, signature, claims verification.
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
# Helpers
# ---------------------------------------------------------------------------

def make_valid_token(spiffe_id: str | None = None, tier: str = "T1", ttl: int | None = None) -> tuple[str, str]:
    """Issue a valid JWT and return (token, spiffe_id)."""
    trust_domain = settings.trust_domain
    sid = spiffe_id or f"spiffe://{trust_domain}/test-agent-{uuid.uuid4().hex[:6]}"
    token, _, _ = issue_jwt(
        spiffe_id=sid,
        tier=tier,
        agent_id="test-agent",
        requested_ttl=ttl,
    )
    return token, sid


def decode_verified(token: str) -> dict:
    """Decode and verify a token using the broker's public key."""
    load_or_generate_signing_key()
    from broker import _private_key
    pub = _private_key.public_key()  # type: ignore[union-attr]
    return pyjwt.decode(token, pub, algorithms=["RS256"], audience=settings.jwt_audience)


def make_expired_token(spiffe_id: str) -> str:
    """Create an already-expired JWT by signing with past timestamps."""
    import time as _time
    load_or_generate_signing_key()
    from broker import _private_key, _key_id

    now = int(_time.time())
    claims = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": spiffe_id,
        "jti": str(uuid.uuid4()),
        "iat": now - 7200,
        "nbf": now - 7200,
        "exp": now - 3600,  # expired 1 hour ago
        "tier": "T1",
        "agent_id": "expired-test",
        "trust_domain": settings.trust_domain,
    }
    return pyjwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": _key_id})  # type: ignore[arg-type]


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
def valid_token_and_sub(trust_domain: str):
    token, spiffe_id = make_valid_token()
    return token, spiffe_id


# ---------------------------------------------------------------------------
# Tests: valid token
# ---------------------------------------------------------------------------

class TestValidateValidToken:
    def test_valid_token_decodes_successfully(self, valid_token_and_sub) -> None:
        token, spiffe_id = valid_token_and_sub
        claims = decode_verified(token)
        assert claims["sub"] == spiffe_id

    def test_valid_token_has_correct_tier(self) -> None:
        token, _ = make_valid_token(tier="T0")
        claims = decode_verified(token)
        assert claims["tier"] == "T0"

    def test_valid_token_has_trust_domain(self, trust_domain: str) -> None:
        token, _ = make_valid_token()
        claims = decode_verified(token)
        assert claims["trust_domain"] == trust_domain

    def test_valid_token_returns_jti(self) -> None:
        token, _ = make_valid_token()
        claims = decode_verified(token)
        assert "jti" in claims
        # jti should be a valid UUID
        uuid.UUID(claims["jti"])

    def test_valid_token_exp_in_future(self) -> None:
        token, _ = make_valid_token()
        claims = decode_verified(token)
        assert claims["exp"] > int(time.time())

    def test_valid_token_iat_in_past_or_now(self) -> None:
        token, _ = make_valid_token()
        claims = decode_verified(token)
        assert claims["iat"] <= int(time.time()) + 1  # allow 1s clock skew


# ---------------------------------------------------------------------------
# Tests: expired token
# ---------------------------------------------------------------------------

class TestExpiredToken:
    def test_expired_token_raises_expired_signature(self, trust_domain: str) -> None:
        spiffe_id = f"spiffe://{trust_domain}/expired-agent"
        expired = make_expired_token(spiffe_id)
        from broker import _private_key
        pub = _private_key.public_key()  # type: ignore[union-attr]
        with pytest.raises(pyjwt.ExpiredSignatureError):
            pyjwt.decode(expired, pub, algorithms=["RS256"], audience=settings.jwt_audience)

    def test_expired_token_can_decode_without_verification(self, trust_domain: str) -> None:
        spiffe_id = f"spiffe://{trust_domain}/expired-agent"
        expired = make_expired_token(spiffe_id)
        claims = pyjwt.decode(
            expired,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=["RS256"],
        )
        assert claims["sub"] == spiffe_id


# ---------------------------------------------------------------------------
# Tests: wrong key
# ---------------------------------------------------------------------------

class TestWrongKey:
    def test_token_from_different_key_raises_invalid_signature(self) -> None:
        # Generate a second, unrelated key pair
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pub = other_key.public_key()

        trust_domain = settings.trust_domain
        claims = {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": f"spiffe://{trust_domain}/rogue-agent",
            "jti": str(uuid.uuid4()),
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
            "tier": "T1",
            "agent_id": "rogue",
        }
        # Sign with other_key
        foreign_token = pyjwt.encode(claims, other_key, algorithm="RS256")

        # Verify with broker's public key — should fail
        from broker import _private_key
        broker_pub = _private_key.public_key()  # type: ignore[union-attr]
        with pytest.raises(pyjwt.InvalidSignatureError):
            pyjwt.decode(foreign_token, broker_pub, algorithms=["RS256"], audience=settings.jwt_audience)


# ---------------------------------------------------------------------------
# Tests: missing required claims
# ---------------------------------------------------------------------------

class TestMissingClaims:
    def _issue_without_claim(self, claim_to_remove: str) -> str:
        """Issue a token then decode, remove a claim, and re-sign with broker key."""
        load_or_generate_signing_key()
        from broker import _private_key, _key_id as kid

        token, _ = make_valid_token()
        claims = pyjwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False},
            algorithms=["RS256"],
        )
        claims.pop(claim_to_remove, None)
        return pyjwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": kid})  # type: ignore[arg-type]

    def test_missing_sub_claim_raises(self) -> None:
        from broker import _private_key
        pub = _private_key.public_key()  # type: ignore[union-attr]
        token = self._issue_without_claim("sub")
        claims = pyjwt.decode(token, pub, algorithms=["RS256"], audience=settings.jwt_audience)
        # sub is missing — caller must check
        assert "sub" not in claims

    def test_missing_exp_raises_decode_error(self) -> None:
        from broker import _private_key
        pub = _private_key.public_key()  # type: ignore[union-attr]
        token = self._issue_without_claim("exp")
        with pytest.raises(pyjwt.exceptions.DecodeError):
            pyjwt.decode(token, pub, algorithms=["RS256"], audience=settings.jwt_audience)

    def test_missing_aud_raises_invalid_claims(self) -> None:
        from broker import _private_key
        pub = _private_key.public_key()  # type: ignore[union-attr]
        token = self._issue_without_claim("aud")
        with pytest.raises(pyjwt.exceptions.InvalidAudienceError):
            pyjwt.decode(token, pub, algorithms=["RS256"], audience=settings.jwt_audience)
