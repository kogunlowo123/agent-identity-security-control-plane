"""Health and readiness endpoints."""

from __future__ import annotations

import logging
import os
import time

import httpx
import psycopg2
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/v1/health", status_code=status.HTTP_200_OK)
async def health() -> dict[str, str]:
    """Liveness probe — always returns 200 if the process is running."""
    return {"status": "ok"}


@router.get("/api/v1/readiness")
async def readiness() -> JSONResponse:
    """
    Readiness probe — checks all upstream dependencies.

    Returns 200 if all dependencies are healthy, 503 otherwise.
    """
    checks: dict[str, str] = {}
    all_ok = True

    # Check database
    db_url = os.getenv("DATABASE_URL", "postgresql://aicp_user:aicp_pass@localhost:5432/aicp_db")
    try:
        conn = psycopg2.connect(db_url, connect_timeout=3)
        conn.close()
        checks["database"] = "ok"
    except Exception as exc:
        logger.warning("Readiness: database check failed: %s", exc)
        checks["database"] = f"error: {type(exc).__name__}"
        all_ok = False

    # Check OPA
    opa_url = os.getenv("OPA_URL", "http://localhost:8181")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{opa_url}/health")
            if resp.status_code == 200:
                checks["opa"] = "ok"
            else:
                checks["opa"] = f"error: HTTP {resp.status_code}"
                all_ok = False
    except Exception as exc:
        logger.warning("Readiness: OPA check failed: %s", exc)
        checks["opa"] = f"error: {type(exc).__name__}"
        all_ok = False

    # Check broker
    broker_url = os.getenv("BROKER_URL", "http://localhost:8100")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{broker_url}/health")
            if resp.status_code == 200:
                checks["broker"] = "ok"
            else:
                checks["broker"] = f"error: HTTP {resp.status_code}"
                all_ok = False
    except Exception as exc:
        logger.warning("Readiness: broker check failed: %s", exc)
        checks["broker"] = f"error: {type(exc).__name__}"
        all_ok = False

    http_status = status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=http_status,
        content={
            "status": "ready" if all_ok else "not_ready",
            "checks": checks,
            "timestamp": int(time.time()),
        },
    )
