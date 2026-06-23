#!/bin/bash
# Cast AI WOOP (Workload Optimization) ROI Projection Report
#
# Point-in-time snapshot of workload rightsizing opportunities across all clusters.
# Categorizes clusters by WOOP adoption and projects CPU/RAM/cost savings.
#
# Usage:
#   ./woop_report.sh --org-id <org_id> --api-key <api_key>
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
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default values
CSV_FILE="woop_report.csv"
MD_FILE="woop_analysis.md"
ORG_ID="${CASTAI_ORG_ID:-}"
API_KEY="${CASTAI_API_KEY:-}"
WOOP_THRESHOLD=50

# Function to print colored messages
log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Cast AI WOOP (Workload Optimization) ROI Projection Report

Fetches workload optimization summaries for all online clusters and generates
a CSV report + Markdown analysis with projected CPU, RAM, and cost savings.

OPTIONS:
    --org-id ID          Cast AI Organization ID (or set CASTAI_ORG_ID)
    --api-key KEY        Cast AI API Key (or set CASTAI_API_KEY)
    --output FILE        Output CSV file (default: woop_report.csv)
    --md-output FILE     Output Markdown file (default: woop_analysis.md)
    --threshold PCT      WOOP adoption threshold % for partial vs active (default: 50)
    -h, --help           Display this help message

EXAMPLE:
    $0 --org-id 4ea1a6e4-ed2e-4aec-9f1c-39fc20b2d8f9 \\
       --api-key your-api-key
EOF
    exit 1
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --org-id)    ORG_ID="$2";        shift 2 ;;
        --api-key)   API_KEY="$2";        shift 2 ;;
        --output)    CSV_FILE="$2";       shift 2 ;;
        --md-output) MD_FILE="$2";        shift 2 ;;
        --threshold) WOOP_THRESHOLD="$2"; shift 2 ;;
        -h|--help)   usage ;;
        *)           log_error "Unknown option: $1"; usage ;;
    esac
done

# Validate required parameters
if [[ -z "$ORG_ID" ]]; then
    log_error "--org-id is required (or set CASTAI_ORG_ID environment variable)"
    usage
fi

if [[ -z "$API_KEY" ]]; then
    log_error "--api-key is required (or set CASTAI_API_KEY environment variable)"
    usage
fi

# Check for required commands
for cmd in curl jq bc; do
    if ! command -v $cmd &> /dev/null; then
        log_error "$cmd command not found. Please install it first."
        exit 1
    fi
done

REPORT_DATE=$(date -u +"%Y-%m-%d %H:%M UTC")

echo "======================================================================"
echo "Cast AI WOOP (Workload Optimization) ROI Projection Report"
echo "======================================================================"
log_info "Organization ID: $ORG_ID"
log_info "Report date:     $REPORT_DATE"
log_info "WOOP threshold:  ${WOOP_THRESHOLD}%"
echo ""

# ─── Step 1: Discover all clusters ──────────────────────────────────────────
log_info "Fetching cluster list..."

CLUSTERS_RESPONSE=$(curl -s -w "\n%{http_code}" --max-time 60 --request GET \
    --url "https://api.cast.ai/v1/kubernetes/external-clusters" \
    --header "X-API-Key: ${API_KEY}" \
    --header "accept: application/json" 2>/dev/null || echo -e "\n000")

CLUSTERS_HTTP_CODE=$(echo "$CLUSTERS_RESPONSE" | tail -n1)
CLUSTERS_BODY=$(echo "$CLUSTERS_RESPONSE" | sed '$d')

if [[ "$CLUSTERS_HTTP_CODE" -ne 200 ]]; then
    log_error "Failed to fetch clusters (HTTP $CLUSTERS_HTTP_CODE)"
    echo "$CLUSTERS_BODY"
    exit 1
fi

# Filter to online clusters only
ONLINE_CLUSTERS=$(echo "$CLUSTERS_BODY" | jq '[.items[] | select(.agentStatus == "online")]')
TOTAL_CLUSTERS=$(echo "$CLUSTERS_BODY" | jq '.items | length')
ONLINE_COUNT=$(echo "$ONLINE_CLUSTERS" | jq 'length')
SKIPPED=$((TOTAL_CLUSTERS - ONLINE_COUNT))

log_success "Found $TOTAL_CLUSTERS clusters total, $ONLINE_COUNT online ($SKIPPED offline/disconnected, skipped)"

# ─── Step 2: Write CSV header ───────────────────────────────────────────────
cat > "$CSV_FILE" << 'CSVHEADER'
cluster_name,providerType,category,totalWorkloads,optimizedCount,optimizedPct,requestedCPU,recommendedCPU,cpuSavings,requestedMemGiB,recommendedMemGiB,memDelta,usageCPU,usageMemGiB,costReqHr,costRecHr,monthlySavings,savingsPct
CSVHEADER

# ─── Step 3: Fetch WOOP summary per cluster ─────────────────────────────────
log_info "Fetching workload optimization summaries..."

# Per-category accumulators (bash 3.2 compatible - no associative arrays)
# Categories: anywhere, no_woop, partial_woop, active_woop, error
ANYWHERE_COUNT=0;      ANYWHERE_CPU_REQ=0;      ANYWHERE_CPU_REC=0;      ANYWHERE_CPU_SAVE=0
ANYWHERE_MEM_REQ=0;    ANYWHERE_MEM_REC=0;      ANYWHERE_MEM_DELTA=0
ANYWHERE_COST_REQ=0;   ANYWHERE_COST_REC=0;     ANYWHERE_WORKLOADS=0;    ANYWHERE_OPTIMIZED=0

NOWOOP_COUNT=0;        NOWOOP_CPU_REQ=0;        NOWOOP_CPU_REC=0;        NOWOOP_CPU_SAVE=0
NOWOOP_MEM_REQ=0;      NOWOOP_MEM_REC=0;        NOWOOP_MEM_DELTA=0
NOWOOP_COST_REQ=0;     NOWOOP_COST_REC=0;       NOWOOP_WORKLOADS=0;      NOWOOP_OPTIMIZED=0

PARTIAL_COUNT=0;       PARTIAL_CPU_REQ=0;       PARTIAL_CPU_REC=0;       PARTIAL_CPU_SAVE=0
PARTIAL_MEM_REQ=0;     PARTIAL_MEM_REC=0;       PARTIAL_MEM_DELTA=0
PARTIAL_COST_REQ=0;    PARTIAL_COST_REC=0;      PARTIAL_WORKLOADS=0;     PARTIAL_OPTIMIZED=0

ACTIVE_COUNT=0;        ACTIVE_CPU_REQ=0;        ACTIVE_CPU_REC=0;        ACTIVE_CPU_SAVE=0
ACTIVE_MEM_REQ=0;      ACTIVE_MEM_REC=0;        ACTIVE_MEM_DELTA=0
ACTIVE_COST_REQ=0;     ACTIVE_COST_REC=0;       ACTIVE_WORKLOADS=0;      ACTIVE_OPTIMIZED=0

ERROR_COUNT=0

# Helper to accumulate into a category
accumulate() {
    local cat="$1"
    local req_cpu="$2" rec_cpu="$3" cpu_save="$4"
    local req_mem="$5" rec_mem="$6" mem_delta="$7"
    local cost_req="$8" cost_rec="$9"
    local workloads="${10}" optimized="${11}"

    case "$cat" in
        anywhere)
            ANYWHERE_COUNT=$((ANYWHERE_COUNT + 1))
            ANYWHERE_CPU_REQ=$(echo "$ANYWHERE_CPU_REQ + $req_cpu" | bc -l)
            ANYWHERE_CPU_REC=$(echo "$ANYWHERE_CPU_REC + $rec_cpu" | bc -l)
            ANYWHERE_CPU_SAVE=$(echo "$ANYWHERE_CPU_SAVE + $cpu_save" | bc -l)
            ANYWHERE_MEM_REQ=$(echo "$ANYWHERE_MEM_REQ + $req_mem" | bc -l)
            ANYWHERE_MEM_REC=$(echo "$ANYWHERE_MEM_REC + $rec_mem" | bc -l)
            ANYWHERE_MEM_DELTA=$(echo "$ANYWHERE_MEM_DELTA + $mem_delta" | bc -l)
            ANYWHERE_COST_REQ=$(echo "$ANYWHERE_COST_REQ + $cost_req" | bc -l)
            ANYWHERE_COST_REC=$(echo "$ANYWHERE_COST_REC + $cost_rec" | bc -l)
            ANYWHERE_WORKLOADS=$((ANYWHERE_WORKLOADS + workloads))
            ANYWHERE_OPTIMIZED=$((ANYWHERE_OPTIMIZED + optimized))
            ;;
        no_woop)
            NOWOOP_COUNT=$((NOWOOP_COUNT + 1))
            NOWOOP_CPU_REQ=$(echo "$NOWOOP_CPU_REQ + $req_cpu" | bc -l)
            NOWOOP_CPU_REC=$(echo "$NOWOOP_CPU_REC + $rec_cpu" | bc -l)
            NOWOOP_CPU_SAVE=$(echo "$NOWOOP_CPU_SAVE + $cpu_save" | bc -l)
            NOWOOP_MEM_REQ=$(echo "$NOWOOP_MEM_REQ + $req_mem" | bc -l)
            NOWOOP_MEM_REC=$(echo "$NOWOOP_MEM_REC + $rec_mem" | bc -l)
            NOWOOP_MEM_DELTA=$(echo "$NOWOOP_MEM_DELTA + $mem_delta" | bc -l)
            NOWOOP_COST_REQ=$(echo "$NOWOOP_COST_REQ + $cost_req" | bc -l)
            NOWOOP_COST_REC=$(echo "$NOWOOP_COST_REC + $cost_rec" | bc -l)
            NOWOOP_WORKLOADS=$((NOWOOP_WORKLOADS + workloads))
            NOWOOP_OPTIMIZED=$((NOWOOP_OPTIMIZED + optimized))
            ;;
        partial_woop)
            PARTIAL_COUNT=$((PARTIAL_COUNT + 1))
            PARTIAL_CPU_REQ=$(echo "$PARTIAL_CPU_REQ + $req_cpu" | bc -l)
            PARTIAL_CPU_REC=$(echo "$PARTIAL_CPU_REC + $rec_cpu" | bc -l)
            PARTIAL_CPU_SAVE=$(echo "$PARTIAL_CPU_SAVE + $cpu_save" | bc -l)
            PARTIAL_MEM_REQ=$(echo "$PARTIAL_MEM_REQ + $req_mem" | bc -l)
            PARTIAL_MEM_REC=$(echo "$PARTIAL_MEM_REC + $rec_mem" | bc -l)
            PARTIAL_MEM_DELTA=$(echo "$PARTIAL_MEM_DELTA + $mem_delta" | bc -l)
            PARTIAL_COST_REQ=$(echo "$PARTIAL_COST_REQ + $cost_req" | bc -l)
            PARTIAL_COST_REC=$(echo "$PARTIAL_COST_REC + $cost_rec" | bc -l)
            PARTIAL_WORKLOADS=$((PARTIAL_WORKLOADS + workloads))
            PARTIAL_OPTIMIZED=$((PARTIAL_OPTIMIZED + optimized))
            ;;
        active_woop)
            ACTIVE_COUNT=$((ACTIVE_COUNT + 1))
            ACTIVE_CPU_REQ=$(echo "$ACTIVE_CPU_REQ + $req_cpu" | bc -l)
            ACTIVE_CPU_REC=$(echo "$ACTIVE_CPU_REC + $rec_cpu" | bc -l)
            ACTIVE_CPU_SAVE=$(echo "$ACTIVE_CPU_SAVE + $cpu_save" | bc -l)
            ACTIVE_MEM_REQ=$(echo "$ACTIVE_MEM_REQ + $req_mem" | bc -l)
            ACTIVE_MEM_REC=$(echo "$ACTIVE_MEM_REC + $rec_mem" | bc -l)
            ACTIVE_MEM_DELTA=$(echo "$ACTIVE_MEM_DELTA + $mem_delta" | bc -l)
            ACTIVE_COST_REQ=$(echo "$ACTIVE_COST_REQ + $cost_req" | bc -l)
            ACTIVE_COST_REC=$(echo "$ACTIVE_COST_REC + $cost_rec" | bc -l)
            ACTIVE_WORKLOADS=$((ACTIVE_WORKLOADS + workloads))
            ACTIVE_OPTIMIZED=$((ACTIVE_OPTIMIZED + optimized))
            ;;
        error)
            ERROR_COUNT=$((ERROR_COUNT + 1))
            ;;
    esac
}

PROCESSED=0

while read -r cluster_json; do
    CLUSTER_ID=$(echo "$cluster_json" | jq -r '.id')
    CLUSTER_NAME=$(echo "$cluster_json" | jq -r '.name')
    PROVIDER_TYPE=$(echo "$cluster_json" | jq -r '.providerType')

    PROCESSED=$((PROCESSED + 1))
    printf "\r${BLUE}[INFO]${NC} Processing cluster %d/%d: %-50s" "$PROCESSED" "$ONLINE_COUNT" "$CLUSTER_NAME"

    # Fetch workloads summary (|| true prevents set -e from killing script on curl timeout)
    SUMMARY_RESPONSE=$(curl -s -w "\n%{http_code}" --max-time 30 \
        "https://api.cast.ai/v1/workload-autoscaling/clusters/${CLUSTER_ID}/workloads-summary?includeCosts=true" \
        -H "X-API-Key: ${API_KEY}" \
        -H "accept: application/json" 2>/dev/null || echo -e "\n000")

    SUMMARY_HTTP_CODE=$(echo "$SUMMARY_RESPONSE" | tail -n1)
    SUMMARY_BODY=$(echo "$SUMMARY_RESPONSE" | sed '$d')

    if [[ "$SUMMARY_HTTP_CODE" -ne 200 ]]; then
        echo "\"$CLUSTER_NAME\",\"$PROVIDER_TYPE\",\"error\",0,0,0,0,0,0,0,0,0,0,0,0,0,0,0" >> "$CSV_FILE"
        accumulate "error" 0 0 0 0 0 0 0 0 0 0
        continue
    fi

    # Extract fields
    TOTAL_COUNT=$(echo "$SUMMARY_BODY"  | jq '.totalCount // 0')
    OPT_COUNT=$(echo "$SUMMARY_BODY"    | jq '.optimizedCount // 0')
    REQ_CPU=$(echo "$SUMMARY_BODY"      | jq '.requestedCpuCores // 0')
    REC_CPU=$(echo "$SUMMARY_BODY"      | jq '.recommendedCpuCores // 0')
    REQ_MEM=$(echo "$SUMMARY_BODY"      | jq '.requestedMemory // 0')
    REC_MEM=$(echo "$SUMMARY_BODY"      | jq '.recommendedMemory // 0')
    USAGE_CPU=$(echo "$SUMMARY_BODY"    | jq '.usageCpuCores // 0')
    USAGE_MEM=$(echo "$SUMMARY_BODY"    | jq '.usageMemoryGibs // 0')
    COST_REQ=$(echo "$SUMMARY_BODY"     | jq '.costsPerHour.requested // 0')
    COST_REC=$(echo "$SUMMARY_BODY"     | jq '.costsPerHour.recommended // 0')

    # Derived values
    if [[ "$TOTAL_COUNT" -gt 0 ]]; then
        OPT_PCT=$(echo "scale=1; $OPT_COUNT * 100 / $TOTAL_COUNT" | bc -l)
    else
        OPT_PCT="0.0"
    fi

    CPU_SAVINGS=$(echo "scale=3; $REQ_CPU - $REC_CPU" | bc -l)
    MONTHLY_SAVE=$(echo "scale=2; ($COST_REQ - $COST_REC) * 730" | bc -l)

    if (( $(echo "$COST_REQ > 0" | bc -l) )); then
        SAVE_PCT=$(echo "scale=1; (1 - $COST_REC / $COST_REQ) * 100" | bc -l)
    else
        SAVE_PCT="0.0"
    fi

    MEM_DELTA=$(echo "scale=3; $REQ_MEM - $REC_MEM" | bc -l)

    # Categorize
    if [[ "$PROVIDER_TYPE" == "anywhere" ]]; then
        CATEGORY="anywhere"
    elif [[ "$OPT_COUNT" -eq 0 ]]; then
        CATEGORY="no_woop"
    elif (( $(echo "$OPT_PCT < $WOOP_THRESHOLD" | bc -l) )); then
        CATEGORY="partial_woop"
    else
        CATEGORY="active_woop"
    fi

    # Write CSV row
    echo "\"$CLUSTER_NAME\",\"$PROVIDER_TYPE\",\"$CATEGORY\",$TOTAL_COUNT,$OPT_COUNT,$OPT_PCT,$REQ_CPU,$REC_CPU,$CPU_SAVINGS,$REQ_MEM,$REC_MEM,$MEM_DELTA,$USAGE_CPU,$USAGE_MEM,$COST_REQ,$COST_REC,$MONTHLY_SAVE,$SAVE_PCT" >> "$CSV_FILE"

    # Accumulate
    accumulate "$CATEGORY" "$REQ_CPU" "$REC_CPU" "$CPU_SAVINGS" "$REQ_MEM" "$REC_MEM" "$MEM_DELTA" "$COST_REQ" "$COST_REC" "$TOTAL_COUNT" "$OPT_COUNT"

done < <(echo "$ONLINE_CLUSTERS" | jq -c '.[]')

echo ""  # newline after progress
echo ""

ROWS=$(wc -l < "$CSV_FILE")
ROWS=$((ROWS - 1))
log_success "CSV file created: $CSV_FILE ($ROWS clusters)"

# ─── Step 4: Grand totals ───────────────────────────────────────────────────
GRAND_CPU_SAVE=$(echo "$ANYWHERE_CPU_SAVE + $NOWOOP_CPU_SAVE + $PARTIAL_CPU_SAVE + $ACTIVE_CPU_SAVE" | bc -l)
GRAND_CPU_REQ=$(echo "$ANYWHERE_CPU_REQ + $NOWOOP_CPU_REQ + $PARTIAL_CPU_REQ + $ACTIVE_CPU_REQ" | bc -l)
GRAND_CPU_REC=$(echo "$ANYWHERE_CPU_REC + $NOWOOP_CPU_REC + $PARTIAL_CPU_REC + $ACTIVE_CPU_REC" | bc -l)
GRAND_MEM_REQ=$(echo "$ANYWHERE_MEM_REQ + $NOWOOP_MEM_REQ + $PARTIAL_MEM_REQ + $ACTIVE_MEM_REQ" | bc -l)
GRAND_MEM_REC=$(echo "$ANYWHERE_MEM_REC + $NOWOOP_MEM_REC + $PARTIAL_MEM_REC + $ACTIVE_MEM_REC" | bc -l)
GRAND_MEM_DELTA=$(echo "$ANYWHERE_MEM_DELTA + $NOWOOP_MEM_DELTA + $PARTIAL_MEM_DELTA + $ACTIVE_MEM_DELTA" | bc -l)
GRAND_COST_REQ=$(echo "$ANYWHERE_COST_REQ + $NOWOOP_COST_REQ + $PARTIAL_COST_REQ + $ACTIVE_COST_REQ" | bc -l)
GRAND_COST_REC=$(echo "$ANYWHERE_COST_REC + $NOWOOP_COST_REC + $PARTIAL_COST_REC + $ACTIVE_COST_REC" | bc -l)
GRAND_WORKLOADS=$((ANYWHERE_WORKLOADS + NOWOOP_WORKLOADS + PARTIAL_WORKLOADS + ACTIVE_WORKLOADS))
GRAND_OPTIMIZED=$((ANYWHERE_OPTIMIZED + NOWOOP_OPTIMIZED + PARTIAL_OPTIMIZED + ACTIVE_OPTIMIZED))

GRAND_MONTHLY=$(echo "scale=2; ($GRAND_COST_REQ - $GRAND_COST_REC) * 730" | bc -l)
GRAND_ANNUAL=$(echo "scale=2; $GRAND_MONTHLY * 12" | bc -l)
if (( $(echo "$GRAND_COST_REQ > 0" | bc -l) )); then
    GRAND_SAVE_PCT=$(echo "scale=1; (1 - $GRAND_COST_REC / $GRAND_COST_REQ) * 100" | bc -l)
else
    GRAND_SAVE_PCT="0.0"
fi

# ─── Step 5: Print summary to stdout ────────────────────────────────────────
print_category_summary() {
    local label="$1" count="$2" cpu_save="$3" mem_delta="$4" cost_req="$5" cost_rec="$6" workloads="$7" optimized="$8"
    [[ "$count" -eq 0 ]] && return

    local monthly=$(echo "scale=0; ($cost_req - $cost_rec) * 730 / 1" | bc -l)
    echo -e "${CYAN}── $label ($count clusters, $workloads workloads, $optimized optimized) ──${NC}"
    printf "  CPU savings:     %.1f cores\n" "$cpu_save"
    printf "  RAM delta:       %.1f GiB (positive=over-provisioned, negative=under-provisioned)\n" "$mem_delta"
    echo "  Monthly savings: \$${monthly}"
    echo ""
}

echo "======================================================================"
echo "WOOP ROI Projection Summary"
echo "======================================================================"
echo ""
echo "Clusters analyzed: $ONLINE_COUNT (of $TOTAL_CLUSTERS total)"
echo "  Anywhere (WOOP-only):   $ANYWHERE_COUNT"
echo "  No WOOP active:         $NOWOOP_COUNT"
echo "  Partial WOOP (<${WOOP_THRESHOLD}%):   $PARTIAL_COUNT"
echo "  Active WOOP (>=${WOOP_THRESHOLD}%):    $ACTIVE_COUNT"
echo "  Errors:                 $ERROR_COUNT"
echo ""

print_category_summary "ANYWHERE (WOOP-only)" "$ANYWHERE_COUNT" "$ANYWHERE_CPU_SAVE" "$ANYWHERE_MEM_DELTA" "$ANYWHERE_COST_REQ" "$ANYWHERE_COST_REC" "$ANYWHERE_WORKLOADS" "$ANYWHERE_OPTIMIZED"
print_category_summary "NO WOOP ACTIVE"       "$NOWOOP_COUNT"   "$NOWOOP_CPU_SAVE"   "$NOWOOP_MEM_DELTA"   "$NOWOOP_COST_REQ"   "$NOWOOP_COST_REC"   "$NOWOOP_WORKLOADS"   "$NOWOOP_OPTIMIZED"
print_category_summary "PARTIAL WOOP"          "$PARTIAL_COUNT"  "$PARTIAL_CPU_SAVE"  "$PARTIAL_MEM_DELTA"  "$PARTIAL_COST_REQ"  "$PARTIAL_COST_REC"  "$PARTIAL_WORKLOADS"  "$PARTIAL_OPTIMIZED"
print_category_summary "ACTIVE WOOP"           "$ACTIVE_COUNT"   "$ACTIVE_CPU_SAVE"   "$ACTIVE_MEM_DELTA"   "$ACTIVE_COST_REQ"   "$ACTIVE_COST_REC"   "$ACTIVE_WORKLOADS"   "$ACTIVE_OPTIMIZED"

echo "======================================================================"
echo -e "${GREEN}GRAND TOTAL${NC}"
echo "======================================================================"
printf "  Total workloads:          %d (%d optimized)\n" "$GRAND_WORKLOADS" "$GRAND_OPTIMIZED"
printf "  CPU: Requested %.1f -> Recommended %.1f cores (%.0f cores savings)\n" \
    "$GRAND_CPU_REQ" "$GRAND_CPU_REC" "$GRAND_CPU_SAVE"
printf "  RAM: Requested %.1f -> Recommended %.1f GiB (%.1f GiB delta)\n" \
    "$GRAND_MEM_REQ" "$GRAND_MEM_REC" "$GRAND_MEM_DELTA"
printf "  Monthly savings:          \$%s (%s%%)\n" "$GRAND_MONTHLY" "$GRAND_SAVE_PCT"
printf "  Annualized:               \$%s\n" "$GRAND_ANNUAL"
echo "======================================================================"

# ─── Step 6: Generate Markdown analysis ─────────────────────────────────────
log_info "Generating Markdown analysis: $MD_FILE"

# Helper: format a table from the CSV for a given category
generate_md_table() {
    local category="$1"
    local has_rows=false
    while IFS=',' read -r name ptype cat total opt optpct reqcpu reccpu cpusave reqmem recmem memdelta ucpu umem creq crec msave spct; do
        # Strip quotes
        cat=$(echo "$cat" | tr -d '"')
        [[ "$cat" != "$category" ]] && continue

        name=$(echo "$name" | tr -d '"')
        ptype=$(echo "$ptype" | tr -d '"')

        if [[ "$has_rows" == "false" ]]; then
            echo "| Cluster | Provider | Workloads | Optimized | CPU Req | CPU Rec | CPU Save | Mem Req GiB | Mem Rec GiB | Mem Delta GiB | Monthly \$ |"
            echo "|---------|----------|-----------|-----------|---------|---------|----------|-------------|-------------|---------------|-----------|"
            has_rows=true
        fi
        printf "| %s | %s | %s | %s (%.0f%%) | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | \$%.0f |\n" \
            "$name" "$ptype" "$total" "$opt" "$optpct" "$reqcpu" "$reccpu" "$cpusave" "$reqmem" "$recmem" "$memdelta" "$msave"
    done < <(tail -n +2 "$CSV_FILE")

    if [[ "$has_rows" == "false" ]]; then
        echo "_No clusters in this category._"
    fi
}

# Compute WOOP adoption rate for key findings
if [[ "$GRAND_WORKLOADS" -gt 0 ]]; then
    WOOP_ADOPTION=$(echo "scale=1; $GRAND_OPTIMIZED * 100 / $GRAND_WORKLOADS" | bc -l)
else
    WOOP_ADOPTION="0.0"
fi

cat > "$MD_FILE" << MDEOF
# WOOP (Workload Optimization) ROI Analysis - Pichincha

**Report date:** $REPORT_DATE
**Organization ID:** $ORG_ID
**Clusters analyzed:** $ONLINE_COUNT of $TOTAL_CLUSTERS

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total workloads | $GRAND_WORKLOADS |
| Workloads optimized by WOOP | $GRAND_OPTIMIZED |
| CPU savings potential | $(printf "%.0f" "$GRAND_CPU_SAVE") cores |
| RAM delta | $(printf "%.1f" "$GRAND_MEM_DELTA") GiB |
| Projected monthly savings | \$$(printf "%.0f" "$GRAND_MONTHLY") |
| Projected annual savings | \$$(printf "%.0f" "$GRAND_ANNUAL") |
| Average cost reduction | ${GRAND_SAVE_PCT}% |

### Cluster Breakdown by WOOP Adoption

| Category | Clusters | Workloads | Optimized | CPU Savings | RAM Delta GiB |
|----------|----------|-----------|-----------|-------------|---------------|
| Anywhere (WOOP-only) | $ANYWHERE_COUNT | $ANYWHERE_WORKLOADS | $ANYWHERE_OPTIMIZED | $(printf "%.1f" "$ANYWHERE_CPU_SAVE") | $(printf "%.1f" "$ANYWHERE_MEM_DELTA") |
| No WOOP | $NOWOOP_COUNT | $NOWOOP_WORKLOADS | $NOWOOP_OPTIMIZED | $(printf "%.1f" "$NOWOOP_CPU_SAVE") | $(printf "%.1f" "$NOWOOP_MEM_DELTA") |
| Partial WOOP | $PARTIAL_COUNT | $PARTIAL_WORKLOADS | $PARTIAL_OPTIMIZED | $(printf "%.1f" "$PARTIAL_CPU_SAVE") | $(printf "%.1f" "$PARTIAL_MEM_DELTA") |
| Active WOOP | $ACTIVE_COUNT | $ACTIVE_WORKLOADS | $ACTIVE_OPTIMIZED | $(printf "%.1f" "$ACTIVE_CPU_SAVE") | $(printf "%.1f" "$ACTIVE_MEM_DELTA") |

---

## Section 1: Anywhere (WOOP-only) Clusters

These clusters run on-premise or bare-metal via CastAI Anywhere. They can only benefit from WOOP (workload rightsizing), not node autoscaling.

$(generate_md_table "anywhere")

> **Key insight:** Anywhere clusters show significant CPU over-provisioning but are often **under-provisioned on RAM** (negative delta). WOOP would right-size memory UP to prevent OOM pressure.

---

## Section 2: Clusters with No WOOP Active

These clusters have **zero workloads** being optimized by WOOP. Full savings are untapped.

$(generate_md_table "no_woop")

---

## Section 3: Clusters with Partial WOOP (<${WOOP_THRESHOLD}%)

These clusters have WOOP enabled on a small fraction of workloads. Most savings are still on the table.

$(generate_md_table "partial_woop")

---

## Section 4: Clusters with Active WOOP (>=${WOOP_THRESHOLD}%)

$(generate_md_table "active_woop")

---

## Key Findings

1. **CPU over-provisioning is widespread:** Across all clusters, **$(printf "%.0f" "$GRAND_CPU_SAVE") CPU cores** can be reclaimed by rightsizing workload requests to match actual usage.

2. **RAM is frequently under-provisioned:** Several clusters (especially production) have workloads using more memory than requested. WOOP would increase RAM requests to safe levels, reducing OOM risk.

3. **WOOP adoption is very low:** Only $GRAND_OPTIMIZED out of $GRAND_WORKLOADS workloads (${WOOP_ADOPTION}%) are being optimized.

4. **Projected savings: \$$(printf "%.0f" "$GRAND_MONTHLY")/month (\$$(printf "%.0f" "$GRAND_ANNUAL")/year)** by enabling WOOP across all clusters.

---

_Generated by woop_report.sh on ${REPORT_DATE}_
MDEOF

log_success "Markdown analysis created: $MD_FILE"

echo ""
echo "======================================================================"
echo "Process completed successfully!"
echo "  CSV report:     $CSV_FILE"
echo "  MD analysis:    $MD_FILE"
echo "======================================================================"
