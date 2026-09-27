# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security vulnerabilities by emailing **kogunlowo@gmail.com** with the subject line:
`[SECURITY] agent-identity-security-control-plane - <brief description>`

### What to Include

1. **Description**: A clear description of the vulnerability
2. **Impact**: Potential impact and attack scenarios
3. **Steps to Reproduce**: Detailed reproduction steps
4. **Affected Components**: Which parts of the system are affected
5. **Suggested Fix**: If you have one (optional)

### Response Timeline

| Action | Timeframe |
|--------|-----------|
| Initial acknowledgment | Within 48 hours |
| Triage and assessment | Within 5 business days |
| Fix development | Depends on severity (Critical: 7 days, High: 14 days, Medium: 30 days) |
| Public disclosure | Coordinated with reporter after fix is deployed |

### Severity Classification

We use CVSS v3.1 for severity ratings:

- **Critical (9.0-10.0)**: Unauthenticated RCE, token forgery, identity impersonation
- **High (7.0-8.9)**: Privilege escalation, authentication bypass, data exfiltration
- **Medium (4.0-6.9)**: Authorization flaws, information disclosure
- **Low (0.1-3.9)**: Minor issues with limited impact

## Security Measures

### Identity Security
- All agent identities are backed by SPIFFE X.509 SVIDs
- JWTs signed with RS256 and rotated per tier TTL
- Token revocation broadcast via Pub/Sub within 1 second
- OPA policies enforce all identity decisions

### Infrastructure Security
- GKE private cluster with authorized networks
- Workload Identity Federation (no static service account keys)
- KMS encryption for etcd secrets and database
- Kyverno admission policies block unsigned images and privileged containers

### Supply Chain Security
- Container images signed with cosign + Rekor transparency log
- SBOM generated for all images (Syft)
- SLSA Level 3 provenance for releases
- Dependabot for automated dependency updates

### Secrets Management
- No secrets in source code or container images
- GCP Secret Manager via External Secrets Operator
- Automatic secret rotation configured

### Monitoring and Detection
- Sigma rules for token burn anomaly and scope violations
- OTel traces for all identity operations
- Audit logs shipped to Cloud Audit Logs
- Error budget burn alerts for SLO violations

## Disclosure Policy

We follow coordinated disclosure. After a fix is deployed, we will:
1. Publish a security advisory on GitHub
2. Credit the reporter (if they wish)
3. Update this document with the CVE if applicable
