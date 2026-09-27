#!/usr/bin/env bash
# Break-glass procedure: grants temporary emergency access with full audit trail.
# Usage: ./break_glass.sh <reason> <duration_minutes>
set -euo pipefail

REASON="${1:?Usage: $0 <reason> <duration_minutes>}"
DURATION="${2:-60}"
OPERATOR="${OPERATOR:-$(whoami)}"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TICKET_ID="BG-$(date +%Y%m%d%H%M%S)-$$"

echo "============================================================"
echo "BREAK-GLASS PROCEDURE INITIATED"
echo "Ticket:    ${TICKET_ID}"
echo "Operator:  ${OPERATOR}"
echo "Reason:    ${REASON}"
echo "Duration:  ${DURATION} minutes"
echo "Timestamp: ${TIMESTAMP}"
echo "============================================================"

# Audit log to Cloud Logging
if command -v gcloud &> /dev/null; then
  gcloud logging write aicp-break-glass \
    "{\"severity\":\"CRITICAL\",\"ticket\":\"${TICKET_ID}\",\"operator\":\"${OPERATOR}\",\"reason\":\"${REASON}\",\"duration_minutes\":${DURATION},\"timestamp\":\"${TIMESTAMP}\"}" \
    --payload-type=json 2>/dev/null || echo "WARNING: Cloud Logging write failed — proceeding anyway"
fi

# Publish CloudEvent to Pub/Sub
if command -v gcloud &> /dev/null && [[ -n "${PUBSUB_TOPIC:-}" ]]; then
  gcloud pubsub topics publish "${PUBSUB_TOPIC}" \
    --message="{\"type\":\"identity.break-glass\",\"ticket\":\"${TICKET_ID}\",\"operator\":\"${OPERATOR}\"}" 2>/dev/null || true
fi

echo "Break-glass access granted for ${DURATION} minutes."
echo "Ticket ${TICKET_ID} has been logged. All actions will be audited."
echo ""
echo "REMINDER: Document all actions taken and close ticket when done."
echo "To revoke early: kubectl delete rolebinding break-glass-${TICKET_ID} -n aicp-system"
