#!/bin/bash
# Cast AI Value Realization Report to CSV Exporter (Bash version)
#
# Usage:
#   ./castai_value_realization_to_csv.sh --start-month 2025-01 --end-month 2025-12 \
#       --org-id <org_id> --api-key <api_key>
#
# Or set environment variables:
#   export CASTAI_ORG_ID=<org_id>
#   export CASTAI_API_KEY=<api_key>

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
OUTPUT_FILE="pichincha_value_realization_report.csv"
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

Export Cast AI Value Realization Report to CSV

OPTIONS:
    --start-month YYYY-MM    Start month (required)
    --end-month YYYY-MM      End month (required)
    --org-id ID              Cast AI Organization ID (or set CASTAI_ORG_ID)
    --api-key KEY            Cast AI API Key (or set CASTAI_API_KEY)
    --output FILE            Output CSV file (default: value_realization_report.csv)
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
for cmd in curl jq date; do
    if ! command -v $cmd &> /dev/null; then
        log_error "$cmd command not found. Please install it first."
        exit 1
    fi
done

# Function to convert YYYY-MM to ISO timestamp
date_to_iso() {
    local input_date="$1"

    # Validate format
    if ! [[ "$input_date" =~ ^[0-9]{4}-[0-9]{2}$ ]]; then
        log_error "Date must be in YYYY-MM format: $input_date"
        exit 1
    fi

    # Convert to ISO format (first day of month at midnight UTC)
    echo "${input_date}-01T00:00:00.000000000Z"
}

# Convert dates to ISO format
START_TIME=$(date_to_iso "$START_MONTH")
END_TIME=$(date_to_iso "$END_MONTH")

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
echo "Cast AI Value Realization Report to CSV Exporter"
echo "======================================================================"

# Step 1: Get cluster IDs
# Query multiple time windows to capture all clusters (some may be added/removed during the period)
log_info "Fetching cluster IDs..."

# Function to fetch clusters for a given month window
fetch_clusters_for_month() {
    local search_month="$1"
    local search_year="${search_month%-*}"
    local search_month_num="${search_month#*-}"

    local start_time="${search_year}-${search_month_num}-28T00:00:00.000000000Z"

    # Calculate end date (28th of next month)
    local end_time
    if [[ "$search_month_num" == "12" ]]; then
        end_time="$((search_year + 1))-01-28T00:00:00.000000000Z"
    else
        end_time="${search_year}-$(printf "%02d" $((10#$search_month_num + 1)))-28T00:00:00.000000000Z"
    fi

    log_info "  Trying: ${start_time} to ${end_time}"

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
        log_warning "  Failed for $search_month (HTTP $http_code)"
        return
    fi

    # Extract cluster IDs (from .clusters array)
    echo "$body" | jq -r '.clusters[].clusterId' 2>/dev/null || true
}

# Collect cluster IDs from both start and end months
ALL_CLUSTER_IDS=""

# Query start month
ALL_CLUSTER_IDS+=$(fetch_clusters_for_month "$START_MONTH")
ALL_CLUSTER_IDS+=$'\n'

# Query end month (if different from start month)
if [[ "$END_MONTH" != "$START_MONTH" ]]; then
    ALL_CLUSTER_IDS+=$(fetch_clusters_for_month "$END_MONTH")
fi

# Remove duplicates, empty lines, and filter only valid UUIDs
CLUSTER_IDS=$(echo "$ALL_CLUSTER_IDS" | sort -u | grep -E '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' || echo "")

if [[ -z "$CLUSTER_IDS" ]]; then
    log_error "No clusters found in any month between $START_MONTH and $END_MONTH"
    exit 1
fi

CLUSTER_COUNT=$(echo "$CLUSTER_IDS" | wc -l)
log_success "Found $CLUSTER_COUNT cluster(s)"

# Build JSON array of cluster IDs
CLUSTER_IDS_JSON=$(echo "$CLUSTER_IDS" | jq -R . | jq -s .)

# Step 2: Get value realization report (chunked by month to avoid API range limits)
log_info "Fetching value realization report..."
log_info "  Organization ID: $ORG_ID"
log_info "  Time range: $START_TIME to $END_TIME"

REQUEST_PAYLOAD=$(jq -n \
    --argjson clusterIds "$CLUSTER_IDS_JSON" \
    '{clusterIds: $clusterIds}')

# Build list of monthly chunks: each chunk is [month_start, next_month_start)
MONTH_CHUNKS=()
CHUNK_YEAR="${START_MONTH%-*}"
CHUNK_MONTH_NUM="${START_MONTH#*-}"

while true; do
    CHUNK_START="${CHUNK_YEAR}-${CHUNK_MONTH_NUM}-01T00:00:00.000000000Z"

    # Calculate next month
    if [[ "$CHUNK_MONTH_NUM" == "12" ]]; then
        NEXT_CHUNK_YEAR=$((CHUNK_YEAR + 1))
        NEXT_CHUNK_MONTH="01"
    else
        NEXT_CHUNK_YEAR=$CHUNK_YEAR
        NEXT_CHUNK_MONTH=$(printf "%02d" $((10#$CHUNK_MONTH_NUM + 1)))
    fi
    CHUNK_END="${NEXT_CHUNK_YEAR}-${NEXT_CHUNK_MONTH}-01T00:00:00.000000000Z"

    MONTH_CHUNKS+=("${CHUNK_START}|${CHUNK_END}")

    # Move to next month
    CHUNK_YEAR=$NEXT_CHUNK_YEAR
    CHUNK_MONTH_NUM=$NEXT_CHUNK_MONTH

    # Stop when we've reached the end time
    if [[ "$CHUNK_END" == "$END_TIME" ]] || [[ "${CHUNK_YEAR}-${CHUNK_MONTH_NUM}" > "${END_TIME:0:7}" ]]; then
        break
    fi
done

log_info "  Splitting into ${#MONTH_CHUNKS[@]} monthly chunk(s)"

# Fetch each monthly chunk and merge timeline items
ALL_TIMELINE_ITEMS="[]"
for chunk in "${MONTH_CHUNKS[@]}"; do
    CHUNK_START="${chunk%|*}"
    CHUNK_END="${chunk#*|}"

    log_info "  Fetching: ${CHUNK_START:0:7}..."

    REPORT_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
        "https://api.cast.ai/reporting/v1beta/organizations/${ORG_ID}:runValueRealizationTimelineReport?startTime=${CHUNK_START}&endTime=${CHUNK_END}&step=ONE_MONTH" \
        -H "accept: application/json" \
        -H "X-API-Key: ${API_KEY}" \
        -H "Content-Type: application/json" \
        -d "$REQUEST_PAYLOAD")

    HTTP_CODE=$(echo "$REPORT_RESPONSE" | tail -n1)
    CHUNK_BODY=$(echo "$REPORT_RESPONSE" | sed '$d')

    if [[ "$HTTP_CODE" -ne 200 ]]; then
        log_warning "  Failed for ${CHUNK_START:0:7} (HTTP $HTTP_CODE)"
        echo "$CHUNK_BODY"
        continue
    fi

    # Merge timeline items
    CHUNK_ITEMS=$(echo "$CHUNK_BODY" | jq '.timelineItems // []')
    ALL_TIMELINE_ITEMS=$(jq -n --argjson existing "$ALL_TIMELINE_ITEMS" --argjson new "$CHUNK_ITEMS" '$existing + $new')
done

# Build final report body with merged timeline items
REPORT_BODY=$(jq -n --argjson items "$ALL_TIMELINE_ITEMS" '{timelineItems: $items}')
ITEM_COUNT=$(echo "$ALL_TIMELINE_ITEMS" | jq 'length')

if [[ "$ITEM_COUNT" -eq 0 ]]; then
    log_error "No data returned from any monthly chunk"
    exit 1
fi

log_success "Successfully fetched value realization report ($ITEM_COUNT monthly data points)"

# Step 3: Convert to CSV
log_info "Writing data to $OUTPUT_FILE..."

# Write CSV header
cat > "$OUTPUT_FILE" << EOF
time_frame,actualCost,projectedCost,autoscalerSavings,workloadAutoscalerSavings,total_savings,cpu_actualCost,cpu_projectedCost,cpu_provisionedCoresHourly,cpu_projectedCoresHourly,cpu_requestedCoresHourly,cpu_provisionedCoreHours,cpu_projectedCoreHours,cpu_requestedCoreHours,memory_actualCost,memory_projectedCost,memory_provisionedBytesHourly,memory_projectedBytesHourly,memory_requestedBytesHourly,memory_provisionedByteHours,memory_projectedByteHours,memory_requestedByteHours
EOF

# Process each timeline item
echo "$REPORT_BODY" | jq -r '
.timelineItems[] |
[
    (.timestamp | sub("T.*"; "") | sub("-([0-9]{2})$"; "-\\1")),
    .cost.actualCost,
    .cost.projectedCost,
    .cost.autoscalerSavings,
    .cost.workloadAutoscalerSavings,
    (.cost.projectedCost - .cost.actualCost),
    .cpu.actualCost,
    .cpu.projectedCost,
    .cpu.provisionedCoresHourly,
    .cpu.projectedCoresHourly,
    .cpu.requestedCoresHourly,
    .cpu.provisionedCoreHours,
    .cpu.projectedCoreHours,
    .cpu.requestedCoreHours,
    .memory.actualCost,
    .memory.projectedCost,
    .memory.provisionedBytesHourly,
    .memory.projectedBytesHourly,
    .memory.requestedBytesHourly,
    .memory.provisionedByteHours,
    .memory.projectedByteHours,
    .memory.requestedByteHours
] | @csv
' >> "$OUTPUT_FILE"

ROWS=$(wc -l < "$OUTPUT_FILE")
ROWS=$((ROWS - 1))  # Subtract header

log_success "CSV file created: $OUTPUT_FILE"
log_info "Total data rows: $ROWS"

echo "======================================================================"
echo "Process completed successfully!"
echo "======================================================================"
