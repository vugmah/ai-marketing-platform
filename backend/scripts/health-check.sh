#!/usr/bin/env bash
# =============================================================================
# Health Check Script for AI Marketing Platform
# =============================================================================
# Performs health checks against running services and reports status.
#
# Usage:
#   ./scripts/health-check.sh [base_url]
#
#   BASE_URL defaults to http://localhost:8000
#
# Examples:
#   ./scripts/health-check.sh
#   ./scripts/health-check.sh https://api.railway.app
#
# Exit codes:
#   0 - All checks passed
#   1 - One or more checks failed
# =============================================================================

set -euo pipefail

# Configuration
BASE_URL="${1:-http://localhost:8000}"
TIMEOUT=10
VERBOSE="${VERBOSE:-0}"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
PASS=0
FAIL=0
WARN=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log_info() {
  echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

check_http() {
  local name="$1"
  local url="$2"
  local expected_code="${3:-200}"
  local result
  local status_code
  local response_body

  if [[ "$VERBOSE" -eq 1 ]]; then
    log_info "Checking $name -> $url"
  fi

  result=$(curl -s -o /dev/null -w "%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null || echo "000")
  status_code="$result"

  if [[ "$status_code" == "$expected_code" ]]; then
    log_info "$name: OK ($status_code)"
    ((PASS++))
  elif [[ "$status_code" == "503" && "$expected_code" == "200" ]]; then
    log_warn "$name: DEGRADED ($status_code)"
    ((WARN++))
  else
    log_error "$name: FAILED (expected $expected_code, got $status_code)"
    ((FAIL++))
  fi
}

check_json_field() {
  local name="$1"
  local url="$2"
  local field="$3"
  local expected_value="$4"
  local response
  local actual_value

  response=$(curl -s --max-time "$TIMEOUT" "$url" 2>/dev/null || echo '{"status": "curl_failed"}')

  actual_value=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin).get('$field', 'FIELD_NOT_FOUND'))" 2>/dev/null || echo "PARSE_ERROR")

  if [[ "$actual_value" == "$expected_value" ]]; then
    log_info "$name: $field=$actual_value"
    ((PASS++))
  else
    log_error "$name: $field expected '$expected_value', got '$actual_value'"
    ((FAIL++))
  fi
}

check_command() {
  local name="$1"
  local cmd="$2"

  if eval "$cmd" > /dev/null 2>&1; then
    log_info "$name: OK"
    ((PASS++))
  else
    log_error "$name: FAILED"
    ((FAIL++))
  fi
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

echo "=========================================="
echo "  AI Marketing Platform - Health Check"
echo "  Target: $BASE_URL"
echo "  Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=========================================="
echo ""

# ---------------------------------------------------------------------------
# Basic connectivity
# ---------------------------------------------------------------------------

echo "--- Basic Connectivity ---"
check_http "Root endpoint" "$BASE_URL/"

# ---------------------------------------------------------------------------
# API v2 Health endpoints
# ---------------------------------------------------------------------------

echo ""
echo "--- Health Endpoints (v2) ---"
check_http "Basic health" "$BASE_URL/api/v2/health/" "200"
check_http "Readiness probe" "$BASE_URL/api/v2/health/ready"
check_http "Liveness probe" "$BASE_URL/api/v2/health/live"
check_json_field "Health status" "$BASE_URL/api/v2/health/" "status" "healthy"

# ---------------------------------------------------------------------------
# Dependency health
# ---------------------------------------------------------------------------

echo ""
echo "--- Dependency Health ---"

# Database
DB_RESPONSE=$(curl -s --max-time "$TIMEOUT" "$BASE_URL/api/v2/health/db" 2>/dev/null || echo '{"status": "unreachable"}')
DB_STATUS=$(echo "$DB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "parse_error")
if [[ "$DB_STATUS" == "healthy" ]]; then
  DB_LATENCY=$(echo "$DB_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('response_time_ms', 'N/A'))" 2>/dev/null || echo "N/A")
  log_info "Database: HEALTHY (latency: ${DB_LATENCY}ms)"
  ((PASS++))
elif [[ "$DB_STATUS" == "degraded" ]]; then
  log_warn "Database: DEGRADED"
  ((WARN++))
else
  log_error "Database: UNHEALTHY ($DB_STATUS)"
  ((FAIL++))
fi

# Redis
REDIS_RESPONSE=$(curl -s --max-time "$TIMEOUT" "$BASE_URL/api/v2/health/redis" 2>/dev/null || echo '{"status": "unreachable"}')
REDIS_STATUS=$(echo "$REDIS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status', 'unknown'))" 2>/dev/null || echo "parse_error")
if [[ "$REDIS_STATUS" == "healthy" ]]; then
  REDIS_LATENCY=$(echo "$REDIS_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('response_time_ms', 'N/A'))" 2>/dev/null || echo "N/A")
  log_info "Redis: HEALTHY (latency: ${REDIS_LATENCY}ms)"
  ((PASS++))
elif [[ "$REDIS_STATUS" == "degraded" ]]; then
  log_warn "Redis: DEGRADED"
  ((WARN++))
else
  log_error "Redis: UNHEALTHY ($REDIS_STATUS)"
  ((FAIL++))
fi

# ---------------------------------------------------------------------------
# Service endpoints
# ---------------------------------------------------------------------------

echo ""
echo "--- Service Endpoints ---"

# Auth
check_http "Auth service" "$BASE_URL/api/v2/auth/health" || true

# Companies
check_http "Companies service" "$BASE_URL/api/v2/companies/" || true

# Dashboard
check_http "Dashboard service" "$BASE_URL/api/v2/dashboard/" || true

# Analytics
check_http "Analytics service" "$BASE_URL/api/v2/analytics/" || true

# ERP
check_http "ERP service" "$BASE_URL/api/v2/erp/health" || true

# ---------------------------------------------------------------------------
# Infrastructure (when running locally)
# ---------------------------------------------------------------------------

echo ""
echo "--- Infrastructure (local) ---"

# Docker containers
if command -v docker &>/dev/null; then
  EXPECTED_CONTAINERS=("aimp_mysql" "aimp_redis" "aimp_backend")
  for container in "${EXPECTED_CONTAINERS[@]}"; do
    if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
      CONTAINER_STATUS=$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || echo "unknown")
      if [[ "$CONTAINER_STATUS" == "running" ]]; then
        log_info "Container $container: running"
        ((PASS++))
      else
        log_warn "Container $container: $CONTAINER_STATUS"
        ((WARN++))
      fi
    else
      log_warn "Container $container: not found"
      ((WARN++))
    fi
  done
else
  log_warn "Docker not available, skipping container checks"
fi

# ---------------------------------------------------------------------------
# Detailed health (verbose)
# ---------------------------------------------------------------------------

if [[ "$VERBOSE" -eq 1 ]]; then
  echo ""
  echo "--- Detailed Health Output ---"
  curl -s --max-time "$TIMEOUT" "$BASE_URL/api/v2/health/detailed" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "Failed to fetch detailed health"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "=========================================="
echo "  Results: $PASS passed, $WARN warnings, $FAIL failed"
echo "=========================================="

if [[ "$FAIL" -gt 0 ]]; then
  echo -e "${RED}STATUS: UNHEALTHY${NC}"
  exit 1
elif [[ "$WARN" -gt 0 ]]; then
  echo -e "${YELLOW}STATUS: DEGRADED${NC}"
  exit 0
else
  echo -e "${GREEN}STATUS: HEALTHY${NC}"
  exit 0
fi
