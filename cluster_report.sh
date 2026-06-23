#!/bin/bash
# Cast AI Cluster Value Realization Report with Baseline Correction
#
# This script fetches per-cluster value realization data and corrects the projected cost
# using actual historical cost data from before Cast AI optimization (firstOperationAt).
#
# Usage:
#   ./cluster_report.sh --start-month 2025-01 --end-month 2025-12 \
#       --org-id <org_id> --api-key <api_key>

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
OUTPUT_FILE="cluster_value_realization_report.csv"
START_MONTH=""
END_MONTH=""
ORG_ID="${CASTAI_ORG_ID:-}"
API_KEY="${CASTAI_API_KEY:-}"

# Function to print colored messages
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to display usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Export Cast AI Per-Cluster Value Realization Report to CSV with Baseline Correction

OPTIONS:
    --start-month YYYY-MM    Start month (required)
    --end-month YYYY-MM      End month (required)
    --org-id ID              Cast AI Organization ID (or set CASTAI_ORG_ID)
    --api-key KEY            Cast AI API Key (or set CASTAI_API_KEY)
    --output FILE            Output CSV file (default: cluster_value_realization_report.csv)
    -h, --help               Display this help message

EXAMPLE:
    $0 --start-month 2025-01 --end-month 2025-12 \\
        --org-id 8cd22cf0-2b9f-4448-b27b-9a0c83ff5356 \\
        --api-key your-api-key
EOF
    exit 1
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --start-month)
            START_MONTH="$2"
            shift 2
            ;;
        --end-month)
            END_MONTH="$2"
            shift 2
            ;;
        --org-id)
            ORG_ID="$2"
            shift 2
            ;;
        --api-key)
            API_KEY="$2"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

# Validate required parameters
if [[ -z "$START_MONTH" ]]; then
    log_error "--start-month is required"
    usage
fi

if [[ -z "$END_MONTH" ]]; then
    log_error "--end-month is required"
    usage
fi

if [[ -z "$ORG_ID" ]]; then
    log_error "--org-id is required (or set CASTAI_ORG_ID environment variable)"
    usage
fi

if [[ -z "$API_KEY" ]]; then
    log_error "--api-key is required (or set CASTAI_API_KEY environment variable)"
    usage
fi

# Check for required commands
for cmd in curl jq date bc; do
    if ! command -v $cmd &> /dev/null; then
        log_error "$cmd command not found. Please install it first."
        exit 1
    fi
done

# Function to convert YYYY-MM to ISO timestamp
date_to_iso() {
    local input_date="$1"
    if ! [[ "$input_date" =~ ^[0-9]{4}-[0-9]{2}$ ]]; then
        log_error "Date must be in YYYY-MM format: $input_date"
        exit 1
    fi
    echo "${input_date}-01T00:00:00.000000000Z"
}

# Convert dates to ISO format
START_TIME=$(date_to_iso "$START_MONTH")

# For end time, move to the first day of the next month
END_YEAR="${END_MONTH%-*}"
END_MONTH_NUM="${END_MONTH#*-}"

if [[ "$END_MONTH_NUM" == "12" ]]; then
    NEXT_YEAR=$((END_YEAR + 1))
    END_TIME="${NEXT_YEAR}-01-01T00:00:00.000000000Z"
else
    NEXT_MONTH=$(printf "%02d" $((10#$END_MONTH_NUM + 1)))
    END_TIME="${END_YEAR}-${NEXT_MONTH}-01T00:00:00.000000000Z"
fi

echo "======================================================================"
echo "Cast AI Cluster Value Realization Report with Baseline Correction"
echo "======================================================================"

# Step 1: Get cluster IDs (reusing logic from app.sh)
log_info "Fetching cluster IDs..."

fetch_clusters_for_month() {
    local search_month="$1"
    local search_year="${search_month%-*}"
    local search_month_num="${search_month#*-}"

    local start_time="${search_year}-${search_month_num}-28T00:00:00.000000000Z"

    local end_time
    if [[ "$search_month_num" == "12" ]]; then
        end_time="$((search_year + 1))-01-28T00:00:00.000000000Z"
    else
        end_time="${search_year}-$(printf "%02d" $((10#$search_month_num + 1)))-28T00:00:00.000000000Z"
    fi

    local response
    response=$(curl -s -w "\n%{http_code}" --request GET \
        --url "https://api.cast.ai/v1/cost-reports/organization/clusters/report?startTime=${start_time}&endTime=${end_time}" \
        --header "X-API-Key: ${API_KEY}" \
        --header "accept: application/json")

    local http_code
    http_code=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | sed '$d')

    if [[ "$http_code" -ne 200 ]]; then
        return
    fi

    echo "$body" | jq -r '.clusters[].clusterId' 2>/dev/null || true
}

ALL_CLUSTER_IDS=""
ALL_CLUSTER_IDS+=$(fetch_clusters_for_month "$START_MONTH")
ALL_CLUSTER_IDS+=$'\n'
if [[ "$END_MONTH" != "$START_MONTH" ]]; then
    ALL_CLUSTER_IDS+=$(fetch_clusters_for_month "$END_MONTH")
fi

CLUSTER_IDS=$(echo "$ALL_CLUSTER_IDS" | sort -u | grep -E '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' || echo "")

if [[ -z "$CLUSTER_IDS" ]]; then
    log_error "No clusters found"
    exit 1
fi

CLUSTER_COUNT=$(echo "$CLUSTER_IDS" | wc -l | tr -d ' ')
log_success "Found $CLUSTER_COUNT cluster(s)"

# Build JSON array of cluster IDs
CLUSTER_IDS_JSON=$(echo "$CLUSTER_IDS" | jq -R . | jq -s .)

# Step 2: Get value realization report for all clusters
log_info "Fetching value realization report..."

REQUEST_PAYLOAD=$(jq -n --argjson clusterIds "$CLUSTER_IDS_JSON" '{clusterIds: $clusterIds}')

REPORT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
    "https://api.cast.ai/reporting/v1beta/organizations/${ORG_ID}/clusters:runValueRealizationReport?startTime=${START_TIME}&endTime=${END_TIME}" \
    -H "accept: application/json" \
    -H "X-API-Key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d "$REQUEST_PAYLOAD")

HTTP_CODE=$(echo "$REPORT_RESPONSE" | tail -n1)
REPORT_BODY=$(echo "$REPORT_RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" -ne 200 ]]; then
    log_error "Failed to fetch value realization report (HTTP $HTTP_CODE)"
    echo "$REPORT_BODY"
    exit 1
fi

log_success "Fetched value realization report"

# Step 3: Process each cluster - get details, baseline cost, and correct projected cost
log_info "Processing clusters and correcting baselines..."

# Write CSV header
cat > "$OUTPUT_FILE" << EOF
cluster_id,cluster_name,firstOperationAt,actualCost,original_projectedCost,corrected_projectedCost,original_totalSavings,corrected_totalSavings,autoscalerSavings,workloadAutoscalerSavings,cpu_actualCost,cpu_projectedCost,memory_actualCost,memory_projectedCost,baseline_daily_cost,baseline_days
EOF

# Calculate number of months in the report period
START_YEAR="${START_MONTH%-*}"
START_MONTH_NUM="${START_MONTH#*-}"
END_YEAR="${END_MONTH%-*}"
END_MONTH_NUM="${END_MONTH#*-}"
REPORT_MONTHS=$(( (END_YEAR - START_YEAR) * 12 + 10#$END_MONTH_NUM - 10#$START_MONTH_NUM + 1 ))

# Process each cluster
echo "$REPORT_BODY" | jq -c '.items[]' | while read -r item; do
    CLUSTER_ID=$(echo "$item" | jq -r '.clusterId')

    log_info "  Processing cluster: $CLUSTER_ID"

    # Get cluster details
    CLUSTER_RESPONSE=$(curl -s -w "\n%{http_code}" --request GET \
        --url "https://api.cast.ai/v1/kubernetes/external-clusters/${CLUSTER_ID}" \
        --header "X-API-Key: ${API_KEY}" \
        --header "accept: application/json")

    CLUSTER_HTTP_CODE=$(echo "$CLUSTER_RESPONSE" | tail -n1)
    CLUSTER_BODY=$(echo "$CLUSTER_RESPONSE" | sed '$d')

    CLUSTER_NAME="unknown"
    FIRST_OPERATION_AT=""
    CREATED_AT=""

    if [[ "$CLUSTER_HTTP_CODE" -eq 200 ]]; then
        CLUSTER_NAME=$(echo "$CLUSTER_BODY" | jq -r '.name // "unknown"')
        FIRST_OPERATION_AT=$(echo "$CLUSTER_BODY" | jq -r '.firstOperationAt // ""')
        CREATED_AT=$(echo "$CLUSTER_BODY" | jq -r '.createdAt // ""')
    else
        log_warning "    Could not fetch cluster details, skipping..."
        continue
    fi

    # Skip clusters without firstOperationAt (not optimized yet)
    if [[ -z "$FIRST_OPERATION_AT" || "$FIRST_OPERATION_AT" == "null" ]]; then
        log_info "    No firstOperationAt (not optimized yet), skipping..."
        continue
    fi

    # Extract values from report
    ACTUAL_COST=$(echo "$item" | jq -r '.cost.actualCost // 0')
    ORIGINAL_PROJECTED_COST=$(echo "$item" | jq -r '.cost.projectedCost // 0')
    AUTOSCALER_SAVINGS=$(echo "$item" | jq -r '.cost.autoscalerSavings // 0')
    WORKLOAD_AUTOSCALER_SAVINGS=$(echo "$item" | jq -r '.cost.workloadAutoscalerSavings // 0')
    ORIGINAL_TOTAL_SAVINGS=$(echo "$item" | jq -r '.cost.totalSavings // 0')
    CPU_ACTUAL_COST=$(echo "$item" | jq -r '.cpu.actualCost // 0')
    CPU_PROJECTED_COST=$(echo "$item" | jq -r '.cpu.projectedCost // 0')
    MEMORY_ACTUAL_COST=$(echo "$item" | jq -r '.memory.actualCost // 0')
    MEMORY_PROJECTED_COST=$(echo "$item" | jq -r '.memory.projectedCost // 0')

    # Default corrected values to original
    CORRECTED_PROJECTED_COST="$ORIGINAL_PROJECTED_COST"
    BASELINE_DAILY_COST="N/A"
    BASELINE_DAYS="0"

    # Fetch baseline cost data (from createdAt to firstOperationAt)
    if [[ -n "$CREATED_AT" && "$CREATED_AT" != "null" ]]; then
        log_info "    Fetching baseline cost (before optimization)..."

        # Get cost data from createdAt to firstOperationAt
        BASELINE_RESPONSE=$(curl -s -w "\n%{http_code}" --request GET \
            --url "https://api.cast.ai/v1/cost-reports/clusters/${CLUSTER_ID}/cost?startTime=${CREATED_AT}&endTime=${FIRST_OPERATION_AT}" \
            --header "X-API-Key: ${API_KEY}" \
            --header "accept: application/json")

        BASELINE_HTTP_CODE=$(echo "$BASELINE_RESPONSE" | tail -n1)
        BASELINE_BODY=$(echo "$BASELINE_RESPONSE" | sed '$d')

        if [[ "$BASELINE_HTTP_CODE" -eq 200 ]]; then
            # Calculate total baseline cost and number of days
            # Handle different response formats and null values
            TOTAL_BASELINE_COST=$(echo "$BASELINE_BODY" | jq '[.items[]? | .totalCost | select(. != null) | (if type == "string" then tonumber else . end)] | add // 0' 2>/dev/null || echo "0")
            BASELINE_DAYS=$(echo "$BASELINE_BODY" | jq '[.items[]? | select(.totalCost != null)] | length' 2>/dev/null || echo "0")

            # Ensure we have valid numbers
            TOTAL_BASELINE_COST=${TOTAL_BASELINE_COST:-0}
            BASELINE_DAYS=${BASELINE_DAYS:-0}

            if [[ "$BASELINE_DAYS" -gt 0 ]] && (( $(echo "$TOTAL_BASELINE_COST > 0" | bc -l 2>/dev/null || echo "0") )); then
                # Calculate daily average cost before optimization
                BASELINE_DAILY_COST=$(echo "scale=6; $TOTAL_BASELINE_COST / $BASELINE_DAYS" | bc -l)

                # Project to the report period (assume 30 days per month)
                REPORT_DAYS=$(( REPORT_MONTHS * 30 ))
                CORRECTED_PROJECTED_COST=$(echo "scale=2; $BASELINE_DAILY_COST * $REPORT_DAYS" | bc -l)

                log_info "    Baseline: $BASELINE_DAYS days, avg daily cost: \$${BASELINE_DAILY_COST}"
            else
                log_warning "    No baseline cost data available"
            fi
        else
            log_warning "    Could not fetch baseline cost data (HTTP $BASELINE_HTTP_CODE)"
        fi
    else
        log_warning "    No createdAt date available"
    fi

    # Calculate corrected total savings
    CORRECTED_TOTAL_SAVINGS=$(echo "scale=2; $CORRECTED_PROJECTED_COST - $ACTUAL_COST" | bc -l)

    # Write to CSV
    echo "\"$CLUSTER_ID\",\"$CLUSTER_NAME\",\"$FIRST_OPERATION_AT\",$ACTUAL_COST,$ORIGINAL_PROJECTED_COST,$CORRECTED_PROJECTED_COST,$ORIGINAL_TOTAL_SAVINGS,$CORRECTED_TOTAL_SAVINGS,$AUTOSCALER_SAVINGS,$WORKLOAD_AUTOSCALER_SAVINGS,$CPU_ACTUAL_COST,$CPU_PROJECTED_COST,$MEMORY_ACTUAL_COST,$MEMORY_PROJECTED_COST,\"$BASELINE_DAILY_COST\",$BASELINE_DAYS" >> "$OUTPUT_FILE"
done

ROWS=$(wc -l < "$OUTPUT_FILE")
ROWS=$((ROWS - 1))

log_success "CSV file created: $OUTPUT_FILE"
log_info "Total clusters processed: $ROWS"

echo "======================================================================"
echo "Process completed successfully!"
echo "======================================================================"
