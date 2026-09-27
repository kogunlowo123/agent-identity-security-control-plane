"""Token revocation API."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="AICP Token Revocation API", version="0.1.0")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aicp_user:aicp_pass@localhost:5432/aicp_db")


class RevokeRequest(BaseModel):
    jti: str
    principal_spiffe_id: str | None = None
    tier: str | None = None
    reason: str = "Manual revocation"
    revoked_by: str = "system"
    ttl_seconds: int = 86400  # How long to keep the revocation record


class RevokeResponse(BaseModel):
    jti: str
    revoked: bool
    message: str


@app.post("/revoke", response_model=RevokeResponse)
async def revoke_token(request: RevokeRequest) -> RevokeResponse:
    """Add a token JTI to the revocation list."""
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO token_revocations (jti, principal_spiffe_id, tier, revoked_at, expires_at, reason, revoked_by)
                VALUES (%s, %s, %s, now(), now() + interval '%s seconds', %s, %s)
                ON CONFLICT (jti) DO NOTHING
                """,
                (
                    request.jti,
                    request.principal_spiffe_id,
                    request.tier,
                    request.ttl_seconds,
                    request.reason,
                    request.revoked_by,
                ),
            )
            conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.error("Failed to revoke token %s: %s", request.jti, exc)
        raise HTTPException(status_code=500, detail="Failed to revoke token") from exc
    finally:
        conn.close()

    logger.info("Revoked token jti=%s reason=%s", request.jti, request.reason)
    return RevokeResponse(jti=request.jti, revoked=True, message="Token revoked successfully")


@app.get("/check/{jti}")
async def check_revocation(jti: str) -> dict[str, bool | str]:
    """Check if a token JTI has been revoked."""
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=5)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT jti, reason, revoked_at FROM token_revocations WHERE jti = %s AND expires_at > now()",
                (jti,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if row:
        return {
            "revoked": True,
            "reason": row["reason"],
            "revoked_at": row["revoked_at"].isoformat(),
        }
    return {"revoked": False}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
