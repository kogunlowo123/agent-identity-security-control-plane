FROM python:3.12-slim AS builder
WORKDIR /build
RUN pip install uv
COPY pyproject.toml uv.lock* ./
RUN uv pip install --system --no-cache .

FROM python:3.12-slim AS runtime
RUN groupadd -r aicp && useradd -r -g aicp -d /app aicp
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY src/ ./src/
RUN chown -R aicp:aicp /app
USER aicp
EXPOSE 8300
CMD ["uvicorn", "src.agent_runtime.main:app", "--host", "0.0.0.0", "--port", "8300"]
