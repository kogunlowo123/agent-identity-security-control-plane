"""
FastAPI application entry point for the Agent Identity Security Control Plane API.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .middleware.auth import AuthMiddleware
from .middleware.ratelimit import RateLimitMiddleware
from .middleware.tenant import TenantMiddleware
from .middleware.tracing import TracingMiddleware
from .routes.v1 import delegation, health, identities

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    app_env: str = "development"
    app_log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql://aicp_user:aicp_pass@localhost:5432/aicp_db"
    broker_url: str = "http://localhost:8100"
    opa_url: str = "http://localhost:8181"
    redis_url: str = "redis://localhost:6379/0"
    otel_endpoint: str = ""
    otel_service_name: str = "aicp-api"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = APISettings()


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------

def setup_telemetry() -> None:
    resource = Resource.create({
        "service.name": settings.otel_service_name,
        "service.version": "0.1.0",
        "deployment.environment": settings.app_env,
    })
    provider = TracerProvider(resource=resource)
    if settings.otel_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


# ---------------------------------------------------------------------------
# Application Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle."""
    logger.info("Starting AICP API service (env=%s)", settings.app_env)
    setup_telemetry()
    # Future: initialize connection pools, verify dependencies
    yield
    logger.info("Shutting down AICP API service")


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Agent Identity Security Control Plane API",
    description=(
        "Enterprise AI security platform providing SPIFFE/SPIRE-based identity issuance, "
        "JWT/SVID lifecycle management, and OPA policy enforcement for AI agents."
    ),
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
    openapi_url="/openapi.json" if settings.app_env != "production" else None,
    lifespan=lifespan,
)

# ── Middleware (order matters: outermost first) ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
app.add_middleware(TracingMiddleware)
app.add_middleware(RateLimitMiddleware, redis_url=settings.redis_url)
app.add_middleware(TenantMiddleware)
# AuthMiddleware is applied per-route via dependency injection (not globally)

# ── OpenTelemetry FastAPI instrumentation ─────────────────────────────────
FastAPIInstrumentor.instrument_app(app)

# ── Routers ───────────────────────────────────────────────────────────────
app.include_router(health.router, tags=["Health"])
app.include_router(identities.router, prefix="/api/v1", tags=["Identities"])
app.include_router(delegation.router, prefix="/api/v1", tags=["Delegation"])


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s: %s", request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred"},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=getattr(logging, settings.app_log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "development",
        log_config=None,
    )
