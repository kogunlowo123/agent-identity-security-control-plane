"""OpenTelemetry trace context propagation middleware."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from opentelemetry import trace
from opentelemetry.propagate import extract
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """
    Propagate OpenTelemetry trace context from incoming headers
    and add trace/span IDs to response headers for client correlation.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Extract trace context from incoming headers (W3C traceparent/tracestate)
        context = extract(dict(request.headers))
        tracer = trace.get_tracer("aicp-api.middleware.tracing")

        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        with tracer.start_as_current_span(
            f"HTTP {request.method} {request.url.path}",
            context=context,
        ) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.request_id", request_id)

            request.state.request_id = request_id
            request.state.trace_id = format(span.get_span_context().trace_id, "032x")

            response = await call_next(request)

            span.set_attribute("http.status_code", response.status_code)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = request.state.trace_id

            return response
