FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install uv

COPY pyproject.toml* uv.lock* ./
COPY broker.py ./

RUN uv pip install --system \
    fastapi>=0.111.0 \
    uvicorn[standard]>=0.29.0 \
    pydantic>=2.0 \
    pydantic-settings>=2.0 \
    PyJWT>=2.8.0 \
    cryptography>=42.0.0 \
    httpx>=0.27.0 \
    opentelemetry-sdk>=1.24.0 \
    opentelemetry-exporter-otlp-proto-grpc>=1.24.0

# ── Runtime stage ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN groupadd -r aicp && useradd -r -g aicp aicp

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY broker.py ./
COPY config.yaml ./
COPY ttl-policies.yaml ./

RUN chown -R aicp:aicp /app
USER aicp

EXPOSE 8100

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')"

CMD ["uvicorn", "broker:app", "--host", "0.0.0.0", "--port", "8100", "--log-config", "none"]
