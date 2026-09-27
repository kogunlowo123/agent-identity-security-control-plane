FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install uv

COPY pyproject.toml uv.lock* ./
RUN uv pip install --system --no-cache .

# ── Runtime ────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN groupadd -r aicp && useradd -r -g aicp -d /app aicp

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY src/ ./src/

RUN chown -R aicp:aicp /app
USER aicp

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-config", "none"]
