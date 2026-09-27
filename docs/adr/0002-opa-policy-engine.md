# ADR 0002: Use OPA for Policy Decisions

**Date**: 2024-01-01
**Status**: Accepted
**Deciders**: kogunlowo123

## Context

The control plane needs to evaluate authorization decisions for identity issuance, delegation, and token validation. Options considered:

1. **Inline Python code** — embed authorization logic directly in the API service
2. **Open Policy Agent (OPA)** — external policy engine with Rego policy language
3. **Cedar** — Amazon's purpose-built authorization language
4. **Casbin** — Go/Python authorization library with multiple enforcement models

## Decision

We will use **Open Policy Agent (OPA)** for all identity policy decisions.

## Rationale

### Arguments for OPA

1. **Policy as Code**: Rego policies are declarative, version-controlled, and auditable. They can be reviewed separately from application code.

2. **Decoupled policy lifecycle**: Policies can be updated and deployed independently of the API service, enabling faster policy iteration without application redeployment.

3. **Audit trail**: OPA can log all decisions with input hashes, providing a complete audit trail for compliance requirements.

4. **Bundle distribution**: OPA's bundle mechanism allows policies to be distributed via GCS, enabling centralized policy management across multiple instances.

5. **CNCF ecosystem**: OPA is a CNCF graduated project used widely for Kubernetes admission control, API authorization, and more. Team familiarity is high.

6. **Testing support**: `opa test` enables unit testing policies before deployment.

### Arguments against alternatives

- **Inline Python**: Authorization logic becomes entangled with application code, making it harder to audit and change independently
- **Cedar**: Immature ecosystem, limited Python tooling
- **Casbin**: Less expressive than Rego for complex hierarchical authorization scenarios

## Consequences

### Positive
- Authorization logic is centralized and auditable
- Policy changes don't require application deployment
- Rego's data model maps naturally to identity claims and delegation chains
- OPA sidecar pattern minimizes latency

### Negative
- OPA adds a dependency and operational surface
- Rego has a learning curve
- Policy performance must be monitored (avoid O(n) policy evaluation)

### Mitigations
- Deploy OPA as a sidecar or cluster-local service to minimize network latency
- Use OPA's partial evaluation to pre-compute decisions where possible
- Include policy unit tests in CI via `opa test`
- Monitor OPA decision latency via OpenTelemetry
