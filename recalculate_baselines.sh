#!/usr/bin/env bash
set -euo pipefail

API_KEY=""
ORG_ID=""
BASE_URL=""

CLUSTERS_FILE="${1:-clusters.txt}"

if [[ ! -f "$CLUSTERS_FILE" ]]; then
  echo "Usage: $0 <clusters_file>"
  echo "File not found: $CLUSTERS_FILE"
  exit 1
fi

while IFS= read -r cluster_id || [[ -n "$cluster_id" ]]; do
  [[ -z "$cluster_id" || "$cluster_id" == \#* ]] && continue

  echo "--- Cluster: $cluster_id"

  response=$(curl -sf -X GET \
    "${BASE_URL}/clusters/${cluster_id}/baseline-params" \
    -H "accept: application/json" \
    -H "X-API-Key: ${API_KEY}") || {
    echo "  ERROR: GET baseline-params failed for $cluster_id"
    continue
  }

  start_time=$(echo "$response" | jq -r '.baselinePeriodStartTime')
  end_time=$(echo "$response" | jq -r '.baselinePeriodEndTime')
  baseline_type=$(echo "$response" | jq -r '.baselineType')

  echo "  baselinePeriodStartTime: $start_time"
  echo "  baselinePeriodEndTime:   $end_time"
  echo "  baselineType:            $baseline_type"

  #if [[ "$baseline_type" == "CLUSTER_HISTORY" ]]; then
  if [[ "$baseline_type" == "CLUSTER_HISTORY" || "$baseline_type" == "PEER_CLUSTERS" ]]; then
    echo "  -> CLUSTER_HISTORY detected, recalculating with INDUSTRY_AVERAGE..."

    recalc_response=$(curl -sf -X POST \
      "${BASE_URL}/clusters/${cluster_id}/baseline-params:recalculate" \
      -H "accept: application/json" \
      -H "X-API-Key: ${API_KEY}" \
      -H "Content-Type: application/json" \
      -d "{
        \"baselineType\": \"INDUSTRY_AVERAGE\",
        \"startTime\": \"${start_time}\",
        \"endTime\": \"${end_time}\"
      }") || {
      echo "  ERROR: POST recalculate failed for $cluster_id"
      continue
    }

    echo "  Recalculate response: $recalc_response"
  else
    echo "  -> baselineType is $baseline_type, skipping recalculate"
  fi

done < "$CLUSTERS_FILE"
