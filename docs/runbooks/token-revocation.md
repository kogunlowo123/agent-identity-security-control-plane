# Runbook: Token Revocation

**Severity**: Varies (P0 for compromised T0/T1, P2 for T3)
**Owner**: Security Platform Team

## When to Use This Runbook

Use this runbook when:
- An agent JWT has been compromised (leaked, credential stuffing, insider threat)
- An agent is decommissioned and its tokens must be immediately invalidated
- A security incident requires revoking all tokens for a given SPIFFE ID

## Step 1: Identify the Token(s) to Revoke

### Option A: Revoke by JTI (single token)
```bash
# Get the JTI from the token
jwt decode <token> | jq .jti

# Or from the audit log
gcloud logging read 'resource.type="k8s_container" AND jsonPayload.jti="<jti>"' \
  --project=$PROJECT_ID --limit=10
```

### Option B: Revoke by agent ID (all tokens for an agent)
```bash
# List active sessions for an agent
psql $DATABASE_URL -c \
  "SELECT session_id, token_jti, started_at FROM sessions WHERE agent_id='<agent-id>' AND status='active';"
```

## Step 2: Add to Revocation List

```bash
# Via API
curl -X POST https://aicp.example.com/api/v1/revoke \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jti": "<jti>", "reason": "Suspected compromise - incident <ID>"}'

# Direct DB insert (break-glass only)
psql $DATABASE_URL -c \
  "INSERT INTO token_revocations (jti, principal_spiffe_id, tier, expires_at, reason, revoked_by)
   VALUES ('<jti>', '<spiffe-id>', '<tier>', now() + interval '24 hours',
           'Suspected compromise - incident <ID>', '$USER');"
```

## Step 3: Broadcast Revocation via Pub/Sub

```bash
# Verify revocation event was published
gcloud pubsub subscriptions pull aicp-identity-revoked-sub \
  --project=$PROJECT_ID --limit=5 --auto-ack
```

## Step 4: Verify Revocation

```bash
# Check the token is now rejected
curl -X POST https://aicp.example.com/api/v1/identities/validate \
  -H "Content-Type: application/json" \
  -d '{"token": "<token>"}'
# Expected: {"valid": false, "error": "Token has been revoked"}
```

## Step 5: Rotate Agent Identity (if compromised)

```bash
# Update the agent registry to revoke the SPIFFE ID
psql $DATABASE_URL -c \
  "UPDATE agent_identities
   SET status='revoked', revoked_at=now(), revocation_reason='Incident <ID>'
   WHERE spiffe_id='<spiffe-id>';"

# Issue a new SPIFFE ID via SPIRE
spire-admin entry create \
  -spiffeID spiffe://agent-identity-security-control-plane/<new-path> \
  -selector k8s:ns:aicp \
  -selector k8s:sa:<service-account>
```

## Step 6: Document the Incident

Create an incident report including:
- Timeline of compromise detection
- JTIs revoked and affected agents
- Root cause analysis
- Remediation steps taken
- Prevention measures

## Rollback

Token revocations are permanent and cannot be undone. If a token was revoked in error:
1. Issue a new token for the agent via `POST /api/v1/identities/issue`
2. Document the incorrect revocation in the incident log
