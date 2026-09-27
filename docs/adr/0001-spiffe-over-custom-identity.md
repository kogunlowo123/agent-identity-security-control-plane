# ADR 0001: Use SPIFFE/SPIRE Over Custom Identity Solution

**Date**: 2024-01-01
**Status**: Accepted
**Deciders**: kogunlowo123

## Context

The Agent Identity Security Control Plane needs a mechanism to issue cryptographic identities to AI agents running in Kubernetes. Several options were considered:

1. **Custom JWT issuance** — generate self-signed JWTs using a custom CA managed by the platform
2. **SPIFFE/SPIRE** — use the SPIFFE standard and SPIRE implementation for workload identity
3. **Service account tokens** — rely purely on Kubernetes service account tokens
4. **mTLS with custom CA** — issue X.509 certificates using an internal CA

## Decision

We will use **SPIFFE/SPIRE** as the identity foundation, with a custom JWT broker for downstream token issuance that builds on SPIFFE SVIDs.

## Rationale

### Arguments for SPIFFE/SPIRE

1. **Industry standard**: SPIFFE is a CNCF graduated project with broad adoption. It provides a well-defined identity API that other systems (Envoy, Istio, SPIFFE-aware applications) can integrate with natively.

2. **Cryptographic attestation**: SPIRE uses node attestation (k8s_psat) to verify workload identity before issuing SVIDs, preventing spoofing at the infrastructure level.

3. **X.509 + JWT SVIDs**: SPIFFE supports both X.509 certificates (for mTLS) and JWT SVIDs (for API authentication), giving us flexibility.

4. **Trust domain model**: The SPIFFE trust domain model maps cleanly to our agent identity hierarchy and aligns with Zero Trust principles (NIST SP 800-207).

5. **No key management burden**: SPIRE manages the CA, key rotation, and certificate issuance automatically, reducing operational burden.

### Arguments against alternatives

- **Custom JWT**: Would require building CA infrastructure, key rotation, attestation — essentially reinventing SPIFFE
- **Service account tokens**: Kubernetes-scoped only, no trust domain concept, not portable
- **Custom mTLS CA**: High operational burden, no standard API for workloads to request certificates

## Consequences

### Positive
- Agents have cryptographically attested identities from day one
- Integration with other SPIFFE-aware infrastructure (Envoy, Istio, OPA) is straightforward
- SVID rotation is automatic via SPIRE agent
- JWT SVIDs can be used directly for API authentication

### Negative
- SPIRE adds operational complexity (SPIRE server + agent DaemonSet)
- SPIRE server is a sensitive component requiring careful HA configuration
- Agents must run in environments with SPIRE agent access

### Mitigations
- Run SPIRE server in HA mode with Kubernetes CRD datastore
- SPIRE agents run as DaemonSet with minimal privileges
- A token broker layer (RFC 8693) provides SPIFFE-backed JWT issuance without exposing SPIRE directly to all callers
