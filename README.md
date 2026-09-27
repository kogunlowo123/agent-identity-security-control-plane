# Agent Identity Security Control Plane

An enterprise-grade AI security platform providing SPIFFE/SPIRE-based identity issuance,
JWT/SVID lifecycle management, OPA policy enforcement, and LangGraph-powered identity audit agents.

## Architecture

```
                    ┌─────────────────────────────────────────────────────┐
                    │              Agent Identity Control Plane            │
                    │                                                       │
  AI Agents  ──────►│  Gateway  ──► API Service  ──► Token Broker         │
                    │               │               (RFC 8693)             │
                    │               ▼                    │                 │
                    │         OPA Policies          SPIRE Server           │
                    │               │               (SPIFFE SVIDs)         │
                    │               ▼                    │                 │
                    │        Identity Registry  ◄────────┘                 │
                    │               │                                       │
                    │               ▼                                       │
                    │        Agent Runtime                                  │
                    │    (LangGraph + LiteLLM)                             │
                    │               │                                       │
                    │               ▼                                       │
                    │          RAG Core                                     │
                    │    (pgvector + OpenSearch)                           │
                    └─────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼               ▼
               Cloud SQL       Pub/Sub           GCS
              (pgvector)    (CloudEvents)    (Artifacts)
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| API | FastAPI + uvicorn |
| Agents | LangGraph 0.2+ |
| LLM Routing | LiteLLM 1.40+ (Vertex AI primary) |
| Identity | SPIFFE/SPIRE + PyJWT + cryptography |
| Policy | Open Policy Agent (OPA) |
| Vector Store | PostgreSQL + pgvector |
| Lexical Search | OpenSearch |
| Embeddings | BAAI/bge-large-en-v1.5 (sentence-transformers) |
| Observability | OpenTelemetry + Grafana |
| Infrastructure | Terraform 1.8+ (GCP) |
| Packaging | uv |
| CI/CD | GitHub Actions + ArgoCD |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/identities/issue` | Issue SVID + JWT for an agent principal |
| POST | `/api/v1/identities/validate` | Validate token, return principal + tier claims |
| GET | `/api/v1/identities/{id}` | Get identity record |
| POST | `/api/v1/delegation/chain` | Create signed delegation link |
| GET | `/api/v1/health` | Liveness probe |
| GET | `/api/v1/readiness` | Readiness probe |

## Agent Families

| Agent | Tier | Capabilities |
|-------|------|-------------|
| `identity-auditor` | T1 | Read identity records, generate audit reports, RAG-grounded analysis |
| `token-inspector` | T0 | Validate token claims, check expiry, report anomalies |
| `spiffe-registrar` | T1 | Manage SPIRE registration entries, sync identity registry |

## Tier System

| Tier | Trust Level | Token TTL | Delegation Depth |
|------|-------------|-----------|-----------------|
| T0 | Highest | 3600s | 0 (cannot delegate) |
| T1 | High | 1800s | 2 |
| T2 | Medium | 900s | 1 |
| T3 | Low | 300s | 0 |

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose
- Terraform 1.8+
- GCP project with billing enabled

### Local Development

```bash
# Clone the repository
git clone https://github.com/kogunlowo123/agent-identity-security-control-plane.git
cd agent-identity-security-control-plane

# Copy environment configuration
cp .env.example .env
# Edit .env with your values

# Start local infrastructure
docker-compose up -d postgres opensearch opa

# Install API service dependencies
cd services/api
uv sync

# Run the API
uv run uvicorn src.api.main:app --reload --port 8000
```

### Running Tests

```bash
# All tests
make test

# Unit tests only
make test-unit

# Integration tests
make test-integration

# Security tests
make test-security
```

### Docker Compose (Full Stack)

```bash
docker-compose up -d
```

Services available:
- API: http://localhost:8000
- OPA: http://localhost:8181
- Broker: http://localhost:8100
- Grafana: http://localhost:3000

## Infrastructure Deployment

### GCP Setup

```bash
# Initialize Terraform for dev environment
cd infra/envs/gcp/dev
terraform init
terraform plan
terraform apply
```

### Production Deployment

```bash
# Apply via CI/CD (recommended)
git push origin main  # triggers terraform.yml workflow

# Or manually
cd infra/envs/gcp/prod
terraform init -backend-config="bucket=your-tfstate-bucket"
terraform apply
```

## Security

See [SECURITY.md](SECURITY.md) for the vulnerability reporting process and security policy.

Key security features:
- SPIFFE/SPIRE cryptographic identity for all agents
- OPA policy enforcement for every identity decision
- Token revocation via Pub/Sub broadcast
- Kyverno policies for Kubernetes admission control
- Cosign image signing with Rekor transparency log
- SBOM generation for all container images
- STRIDE threat model documented in `security/threat-models/`

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

## License

Apache 2.0 — see [LICENSE](LICENSE).
