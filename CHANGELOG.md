# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2024-01-01

### Added

#### Core Identity Platform
- SPIFFE/SPIRE-based identity issuance for AI agents with trust domain `agent-identity-security-control-plane`
- JWT token lifecycle management with RS256 signing (issue, validate, revoke, rotate)
- Tier-based agent identity system: T0 (3600s TTL), T1 (1800s TTL), T2 (900s TTL), T3 (300s TTL)
- YAML-based agent identity registry with JSON Schema validation
- RFC 8693 compliant token exchange broker with JWKS endpoint
- Token revocation via PostgreSQL revocation list + Pub/Sub broadcast

#### OPA Policy Engine
- `identity.rego`: identity issuance policies, tier-based TTL caps, SVID validation
- `delegation.rego`: delegation chain validation, capability subset enforcement, depth limits
- Per-tier delegation depth limits: T0=0, T1=2, T2=1, T3=0

#### API Service
- `POST /api/v1/identities/issue` — issue SVID + JWT for agent principal
- `POST /api/v1/identities/validate` — validate token with principal claims
- `GET /api/v1/identities/{id}` — retrieve identity record
- `POST /api/v1/delegation/chain` — create signed delegation chain
- `GET /api/v1/health` — liveness probe
- `GET /api/v1/readiness` — readiness probe with dependency checks
- OpenTelemetry tracing on all routes
- Per-tier rate limiting middleware

#### Agent Runtime
- LangGraph-powered identity audit agents with typed state graphs
- Agent families: `identity-auditor` (T1), `token-inspector` (T0), `spiffe-registrar` (T1)
- Hybrid RAG retrieval: BM25 (OpenSearch) + dense (pgvector) with RRF fusion
- Grounding check guardrail before agent output
- Budget enforcement per session and tier
- Human approval gates for sensitive operations

#### RAG Core
- Document ingestion pipeline: PDF, HTML loaders with GCS sync
- Multiple chunking strategies: recursive, semantic, structural, parent-child
- Metadata enrichment: PII tagging, ACL stamping, auto-tagging
- Embedding providers: Vertex AI text-embedding-004, local BAAI/bge-large-en-v1.5
- Hybrid retrieval with Reciprocal Rank Fusion (k=60)
- Cross-encoder reranker for final ranking

#### Infrastructure (GCP)
- GKE private cluster with Workload Identity Federation
- Cloud SQL PostgreSQL with pgvector extension
- Pub/Sub topics for CloudEvents: identity.issued, identity.revoked, identity.violated
- KMS encryption for etcd secrets and application data
- IAM service accounts with least-privilege bindings
- GCS buckets for artifacts, models, audit logs

#### Security
- Kyverno policies: require signed images, disallow privileged containers
- Sigma detection rules: token burn anomaly, scope violations
- STRIDE threat model for the identity plane
- Cosign image signing with Rekor transparency log integration
- SLSA Level 3 provenance for releases

#### Observability
- OpenTelemetry Collector with GCP trace/metrics exporters
- Grafana dashboards: platform overview, identity events
- Prometheus alerting rules: error budget burn, revocation latency

#### CI/CD
- GitHub Actions: lint, type-check, unit tests, integration tests
- Terraform workflow: fmt, validate, tflint, checkov, plan/apply via OIDC
- Security workflow: CodeQL, Trivy, Gitleaks, SBOM generation
- Release workflow: build, sign, SLSA provenance, GitHub release

[Unreleased]: https://github.com/kogunlowo123/agent-identity-security-control-plane/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kogunlowo123/agent-identity-security-control-plane/releases/tag/v0.1.0
