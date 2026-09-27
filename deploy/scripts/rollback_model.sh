#!/usr/bin/env bash
# Rollback LLM model routing to a previous configuration.
# Usage: ./rollback_model.sh <namespace> <deployment> <previous_model_config>
set -euo pipefail

NAMESPACE="${1:?Usage: $0 <namespace> <deployment> <config_key>}"
DEPLOYMENT="${2:?Deployment name required}"
CONFIG_KEY="${3:?Config key required (e.g. gemini-1.5-flash)}"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "Rolling back model config for ${DEPLOYMENT} in ${NAMESPACE} to ${CONFIG_KEY} at ${TIMESTAMP}"

if ! command -v kubectl &> /dev/null; then
  echo "ERROR: kubectl not found" >&2
  exit 1
fi

kubectl set env "deployment/${DEPLOYMENT}" \
  -n "${NAMESPACE}" \
  "DEFAULT_LLM_MODEL=${CONFIG_KEY}"

kubectl rollout status "deployment/${DEPLOYMENT}" -n "${NAMESPACE}" --timeout=120s

echo "Rollback complete. Verifying pods..."
kubectl get pods -n "${NAMESPACE}" -l "app=${DEPLOYMENT}" --no-headers

echo "Model rollback to ${CONFIG_KEY} completed successfully."
