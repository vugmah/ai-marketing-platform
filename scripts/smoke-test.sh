#!/bin/bash
# =============================================================================
# AI Marketing Platform - Smoke Test Suite
# =============================================================================
# Comprehensive smoke tests for API health, authentication, and CRUD operations.
# Designed to run after deployments (CI/CD or manual) to verify system health.
#
# Usage:
#   ./scripts/smoke-test.sh                    # Run all tests
#   ./scripts/smoke-test.sh --local            # Test local Docker setup
#   ./scripts/smoke-test.sh --railway          # Test Railway deployment
#   ./scripts/smoke-test.sh --health-only      # Only health checks
#   ./scripts/smoke-test.sh --auth-only        # Only auth tests
#   ./scripts/smoke-test.sh --crud-only        # Only CRUD tests
#   ./scripts/smoke-test.sh --verbose          # Verbose output
#
# Exit Codes:
#   0  - All tests passed
#   1  - One or more tests failed
# =============================================================================

set -u

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TARGET="${TARGET:-local}"
API_URL="${API_URL:-http://localhost:8000}"
VERBOSE=false
RUN_HEALTH=true
RUN_AUTH=true
RUN_CRUD=true
RUN_PERFORMANCE=true
RUN_MONITORING=true

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0
WARNINGS=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_section()  { echo -e "\n${BLUE}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; echo -e "${BLUE}${BOLD}  $*${NC}"; echo -e "${BLUE}${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"; }
log_info()     { echo -e "${BLUE}[INFO]${NC}  $(date '+%H:%M:%S') | $*"; }
log_pass()     { echo -e "${GREEN}[PASS]${NC}  $(date '+%H:%M:%S') | $*"; ((TESTS_PASSED++)); }
log_fail()     { echo -e "${RED}[FAIL]${NC}  $(date '+%H:%M:%S') | $*"; ((TESTS_FAILED++)); }
log_skip()     { echo -e "${YELLOW}[SKIP]${NC}  $(date '+%H:%M:%S') | $*"; ((TESTS_SKIPPED++)); }
log_warn()     { echo -e "${YELLOW}[WARN]${NC}  $(date '+%H:%M:%S') | $*"; ((WARNINGS++)); }
log_detail()   { [[ "$VERBOSE" == true ]] && echo -e "        | $*"; }

# ---------------------------------------------------------------------------
# HTTP utilities
# ---------------------------------------------------------------------------
http_get() {
    local url="$1"
    local extra_args="${2:-}"
    curl -s -o /dev/null -w "%{http_code}|%{time_total}|%{size_download}" \
         -H "Accept: application/json" \
         $extra_args \
         --max-time 15 "$url" 2>/dev/null || echo "000|0|0"
}

http_post() {
    local url="$1"
    local data="$2"
    local extra_args="${3:-}"
    curl -s -o /dev/null -w "%{http_code}|%{time_total}|%{size_download}" \
         -H "Content-Type: application/json" \
         -H "Accept: application/json" \
         $extra_args \
         --max-time 15 \
         -d "$data" "$url" 2>/dev/null || echo "000|0|0"
}

http_delete() {
    local url="$1"
    local extra_args="${2:-}"
    curl -s -o /dev/null -w "%{http_code}|%{time_total}|%{size_download}" \
         -H "Accept: application/json" \
         -X DELETE \
         $extra_args \
         --max-time 15 "$url" 2>/dev/null || echo "000|0|0"
}

http_response_body() {
    local url="$1"
    local extra_args="${2:-}"
    curl -s -H "Accept: application/json" \
         $extra_args \
         --max-time 15 "$url" 2>/dev/null || echo ""
}

assert_status() {
    local test_name="$1"
    local status="$2"
    local expected="$3"
    local duration="$4"
    if [[ "$status" == "$expected" ]]; then
        log_pass "${test_name} (HTTP ${status}, ${duration}s)"
        return 0
    else
        log_fail "${test_name} (expected HTTP ${expected}, got ${status})"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --local)
            TARGET="local"
            API_URL="http://localhost:8000"
            shift
            ;;
        --railway)
            TARGET="railway"
            API_URL="${RAILWAY_URL:-https://aimp.up.railway.app}"
            shift
            ;;
        --url)
            API_URL="$2"
            shift 2
            ;;
        --health-only)
            RUN_AUTH=false
            RUN_CRUD=false
            RUN_PERFORMANCE=false
            RUN_MONITORING=false
            shift
            ;;
        --auth-only)
            RUN_HEALTH=false
            RUN_CRUD=false
            RUN_PERFORMANCE=false
            RUN_MONITORING=false
            shift
            ;;
        --crud-only)
            RUN_HEALTH=false
            RUN_AUTH=false
            RUN_PERFORMANCE=false
            RUN_MONITORING=false
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--local|--railway] [--url URL] [--health-only|--auth-only|--crud-only] [--verbose]"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
log_section "SMOKE TEST SUITE - AI Marketing Platform v2.0.0"
echo "  Target:  ${TARGET}"
echo "  API URL: ${API_URL}"
echo "  Time:    $(date '+%Y-%m-%d %H:%M:%S %Z')"

# Check curl is available
if ! command -v curl &>/dev/null; then
    echo "ERROR: curl is required but not installed"
    exit 1
fi

# Wait for API to be available
log_info "Checking API availability..."
MAX_WAIT=60
WAITED=0
while [[ $WAITED -lt $MAX_WAIT ]]; do
    RESPONSE=$(http_get "${API_URL}/api/v2/health/live")
    STATUS=${RESPONSE%%|*}
    if [[ "$STATUS" == "200" ]]; then
        log_ok "API is reachable"
        break
    fi
    echo -n "."
    sleep 2
    ((WAITED+=2))
done

if [[ $WAITED -ge $MAX_WAIT ]]; then
    log_fail "API is not reachable after ${MAX_WAIT}s"
    echo "  Is the API running at ${API_URL}?"
    exit 1
fi

# ---------------------------------------------------------------------------
# TEST GROUP 1: Health Checks
# ---------------------------------------------------------------------------
if [[ "$RUN_HEALTH" == true ]]; then
    log_section "HEALTH CHECKS"

    # Test 1.1: Liveness probe
    RESPONSE=$(http_get "${API_URL}/api/v2/health/live")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    assert_status "Liveness probe" "$STATUS" "200" "$DURATION"
    BODY=$(http_response_body "${API_URL}/api/v2/health/live")
    log_detail "Response: ${BODY:0:200}"

    # Test 1.2: Readiness probe
    RESPONSE=$(http_get "${API_URL}/api/v2/health/ready")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    assert_status "Readiness probe" "$STATUS" "200" "$DURATION"
    BODY=$(http_response_body "${API_URL}/api/v2/health/ready")
    log_detail "Response: ${BODY:0:200}"

    # Test 1.3: Detailed health check
    RESPONSE=$(http_get "${API_URL}/api/v2/health/detailed")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    assert_status "Detailed health" "$STATUS" "200" "$DURATION"

    # Test 1.4: Database health
    RESPONSE=$(http_get "${API_URL}/api/v2/health/db")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    assert_status "Database health" "$STATUS" "200" "$DURATION"

    # Test 1.5: Redis health
    RESPONSE=$(http_get "${API_URL}/api/v2/health/redis")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    assert_status "Redis health" "$STATUS" "200" "$DURATION"

    # Test 1.6: Prometheus metrics
    RESPONSE=$(http_get "${API_URL}/api/v2/health/metrics")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    assert_status "Prometheus metrics" "$STATUS" "200" "$DURATION"
    METRICS_SIZE=$(echo "$RESPONSE" | cut -d'|' -f3)
    if [[ "$METRICS_SIZE" -gt 500 ]]; then
        log_pass "Metrics payload size: ${METRICS_SIZE} bytes"
    else
        log_warn "Metrics payload seems small: ${METRICS_SIZE} bytes"
    fi

    # Test 1.7: API docs (OpenAPI)
    RESPONSE=$(http_get "${API_URL}/api/openapi.json")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    assert_status "OpenAPI schema" "$STATUS" "200" "$DURATION"

    # Test 1.8: Response headers check
    CORRELATION_HEADER=$(curl -sI "${API_URL}/api/v2/health/live" 2>/dev/null | grep -i 'x-correlation-id' || true)
    if [[ -n "$CORRELATION_HEADER" ]]; then
        log_pass "Correlation ID header present"
    else
        log_warn "Correlation ID header missing"
    fi
fi

# ---------------------------------------------------------------------------
# TEST GROUP 2: Authentication
# ---------------------------------------------------------------------------
if [[ "$RUN_AUTH" == true ]]; then
    log_section "AUTHENTICATION TESTS"

    # Test 2.1: Login with invalid credentials (should return 401)
    RESPONSE=$(http_post "${API_URL}/api/v2/auth/login" '{"email":"invalid@test.com","password":"wrong"}')
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "401" ]] || [[ "$STATUS" == "422" ]]; then
        log_pass "Invalid login rejected (HTTP ${STATUS})"
    else
        log_warn "Unexpected status for invalid login: ${STATUS} (expected 401/422)"
    fi

    # Test 2.2: Login endpoint accepts request
    RESPONSE=$(http_post "${API_URL}/api/v2/auth/login" '{"email":"admin@example.com","password":"password123"}')
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]] || [[ "$STATUS" == "422" ]]; then
        log_pass "Login endpoint reachable (HTTP ${STATUS})"
    else
        log_warn "Login returned unexpected status: ${STATUS}"
    fi

    # Test 2.3: Protected endpoint without auth (should return 401/403)
    RESPONSE=$(http_get "${API_URL}/api/v2/companies/")
    STATUS=${RESPONSE%%|*}
    if [[ "$STATUS" == "401" ]] || [[ "$STATUS" == "403" ]] || [[ "$STATUS" == "422" ]]; then
        log_pass "Protected endpoint rejects unauthenticated access (HTTP ${STATUS})"
    elif [[ "$STATUS" == "200" ]]; then
        log_warn "Protected endpoint returned 200 without auth - verify middleware"
    else
        log_info "Protected endpoint status: ${STATUS}"
    fi

    # Test 2.4: Registration endpoint
    RESPONSE=$(http_post "${API_URL}/api/v2/auth/register" '{"email":"smoketest@example.com","password":"Test123!","name":"Smoke Test"}')
    STATUS=${RESPONSE%%|*}
    if [[ "$STATUS" == "201" ]] || [[ "$STATUS" == "200" ]]; then
        log_pass "Registration endpoint working (HTTP ${STATUS})"
    elif [[ "$STATUS" == "409" ]] || [[ "$STATUS" == "422" ]]; then
        log_pass "Registration validation working (HTTP ${STATUS})"
    else
        log_info "Registration status: ${STATUS}"
    fi

    # Test 2.5: Token refresh endpoint structure
    RESPONSE=$(http_post "${API_URL}/api/v2/auth/refresh" '{"refresh_token":"invalid"}')
    STATUS=${RESPONSE%%|*}
    if [[ "$STATUS" == "401" ]] || [[ "$STATUS" == "422" ]] || [[ "$STATUS" == "200" ]]; then
        log_pass "Token refresh endpoint reachable (HTTP ${STATUS})"
    else
        log_info "Token refresh status: ${STATUS}"
    fi
fi

# ---------------------------------------------------------------------------
# TEST GROUP 3: CRUD Operations
# ---------------------------------------------------------------------------
if [[ "$RUN_CRUD" == true ]]; then
    log_section "CRUD OPERATION TESTS"

    # Test 3.1: Companies list (public endpoint behavior)
    RESPONSE=$(http_get "${API_URL}/api/v2/companies/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    assert_status "GET /companies" "$STATUS" "200" "$DURATION"

    # Test 3.2: Branches list
    RESPONSE=$(http_get "${API_URL}/api/v2/branches/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /branches (HTTP ${STATUS})"
    else
        log_info "GET /branches status: ${STATUS}"
    fi

    # Test 3.3: Analytics endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/analytics/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /analytics (HTTP ${STATUS})"
    else
        log_info "GET /analytics status: ${STATUS}"
    fi

    # Test 3.4: AI endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/ai/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /ai (HTTP ${STATUS})"
    else
        log_info "GET /ai status: ${STATUS}"
    fi

    # Test 3.5: Social media endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/social/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /social (HTTP ${STATUS})"
    else
        log_info "GET /social status: ${STATUS}"
    fi

    # Test 3.6: Media endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/media/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /media (HTTP ${STATUS})"
    else
        log_info "GET /media status: ${STATUS}"
    fi

    # Test 3.7: Events endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/events/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /events (HTTP ${STATUS})"
    else
        log_info "GET /events status: ${STATUS}"
    fi

    # Test 3.8: Billing endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/billing/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /billing (HTTP ${STATUS})"
    else
        log_info "GET /billing status: ${STATUS}"
    fi

    # Test 3.9: Notifications endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/notifications/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /notifications (HTTP ${STATUS})"
    else
        log_info "GET /notifications status: ${STATUS}"
    fi

    # Test 3.10: Audit endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/audit/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /audit (HTTP ${STATUS})"
    else
        log_info "GET /audit status: ${STATUS}"
    fi

    # Test 3.11: Support endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/support/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /support (HTTP ${STATUS})"
    else
        log_info "GET /support status: ${STATUS}"
    fi

    # Test 3.12: Ads endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/ads/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /ads (HTTP ${STATUS})"
    else
        log_info "GET /ads status: ${STATUS}"
    fi

    # Test 3.13: Dashboard endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/dashboard/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /dashboard (HTTP ${STATUS})"
    else
        log_info "GET /dashboard status: ${STATUS}"
    fi

    # Test 3.14: ERP endpoint
    RESPONSE=$(http_get "${API_URL}/api/v2/erp/")
    STATUS=${RESPONSE%%|*}
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if [[ "$STATUS" == "200" ]] || [[ "$STATUS" == "401" ]]; then
        log_pass "GET /erp (HTTP ${STATUS})"
    else
        log_info "GET /erp status: ${STATUS}"
    fi

    # Test 3.15: 404 handling
    RESPONSE=$(http_get "${API_URL}/api/v2/nonexistent-endpoint")
    STATUS=${RESPONSE%%|*}
    if [[ "$STATUS" == "404" ]]; then
        log_pass "404 handling works (HTTP ${STATUS})"
    else
        log_warn "404 returned ${STATUS} instead of 404"
    fi

    # Test 3.16: Method not allowed
    RESPONSE=$(http_delete "${API_URL}/api/v2/health/live")
    STATUS=${RESPONSE%%|*}
    if [[ "$STATUS" == "405" ]]; then
        log_pass "Method not allowed handling (HTTP ${STATUS})"
    else
        log_info "DELETE health status: ${STATUS}"
    fi

    # Test 3.17: CORS preflight
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X OPTIONS \
        -H "Origin: http://localhost:3000" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type,Authorization" \
        --max-time 10 \
        "${API_URL}/api/v2/auth/login" 2>/dev/null || echo "000")
    if [[ "$RESPONSE" == "200" ]] || [[ "$RESPONSE" == "204" ]]; then
        log_pass "CORS preflight works (HTTP ${RESPONSE})"
    else
        log_info "CORS preflight status: ${RESPONSE}"
    fi

    # Test 3.18: Content-Type validation
    RESPONSE=$(http_post "${API_URL}/api/v2/auth/login" "not-json")
    STATUS=${RESPONSE%%|*}
    if [[ "$STATUS" == "422" ]] || [[ "$STATUS" == "400" ]]; then
        log_pass "Invalid JSON rejected (HTTP ${STATUS})"
    else
        log_info "Invalid JSON status: ${STATUS}"
    fi
fi

# ---------------------------------------------------------------------------
# TEST GROUP 4: Performance Tests
# ---------------------------------------------------------------------------
if [[ "$RUN_PERFORMANCE" == true ]]; then
    log_section "PERFORMANCE TESTS"

    # Test 4.1: Health check latency
    RESPONSE=$(http_get "${API_URL}/api/v2/health/live")
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    DURATION_MS=$(echo "$DURATION * 1000" | bc 2>/dev/null || echo "100")
    if (( $(echo "$DURATION < 0.5" | bc 2>/dev/null || echo "0") )); then
        log_pass "Health check latency: ${DURATION}s (< 500ms)"
    else
        log_warn "Health check latency: ${DURATION}s (should be < 500ms)"
    fi

    # Test 4.2: Concurrent request test (10 parallel requests)
    log_info "Testing 10 concurrent health checks..."
    CONCURRENT_START=$(date +%s%N)
    for i in {1..10}; do
        http_get "${API_URL}/api/v2/health/live" &
    done
    wait
    CONCURRENT_END=$(date +%s%N)
    CONCURRENT_MS=$(( (CONCURRENT_END - CONCURRENT_START) / 1000000 ))
    if [[ $CONCURRENT_MS -lt 5000 ]]; then
        log_pass "10 concurrent requests in ${CONCURRENT_MS}ms"
    else
        log_warn "10 concurrent requests took ${CONCURRENT_MS}ms (should be < 5000ms)"
    fi

    # Test 4.3: Metrics endpoint performance
    RESPONSE=$(http_get "${API_URL}/api/v2/health/metrics")
    DURATION=$(echo "$RESPONSE" | cut -d'|' -f2)
    if (( $(echo "$DURATION < 1.0" | bc 2>/dev/null || echo "0") )); then
        log_pass "Metrics endpoint: ${DURATION}s"
    else
        log_warn "Metrics endpoint slow: ${DURATION}s"
    fi
fi

# ---------------------------------------------------------------------------
# TEST GROUP 5: Monitoring Stack
# ---------------------------------------------------------------------------
if [[ "$RUN_MONITORING" == true && "$TARGET" == "local" ]]; then
    log_section "MONITORING STACK CHECKS"

    # Test 5.1: Prometheus reachable
    RESPONSE=$(http_get "http://localhost:9090/-/healthy" 2>/dev/null || echo "000|0|0")
    STATUS=${RESPONSE%%|*}
    if [[ "$STATUS" == "200" ]]; then
        log_pass "Prometheus is healthy"
    else
        log_skip "Prometheus not available (local only)"
    fi

    # Test 5.2: Grafana reachable
    RESPONSE=$(http_get "http://localhost:3001/api/health" 2>/dev/null || echo "000|0|0")
    STATUS=${RESPONSE%%|*}
    if [[ "$STATUS" == "200" ]]; then
        log_pass "Grafana is healthy"
    else
        log_skip "Grafana not available (local only)"
    fi

    # Test 5.3: Alertmanager reachable
    RESPONSE=$(http_get "http://localhost:9093/-/healthy" 2>/dev/null || echo "000|0|0")
    STATUS=${RESPONSE%%|*}
    if [[ "$STATUS" == "200" ]]; then
        log_pass "Alertmanager is healthy"
    else
        log_skip "Alertmanager not available (local only)"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log_section "TEST SUMMARY"

TOTAL=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))
echo "  Total Tests:    ${TOTAL}"
echo -e "  ${GREEN}Passed:${NC}         ${TESTS_PASSED}"
echo -e "  ${RED}Failed:${NC}         ${TESTS_FAILED}"
echo -e "  ${YELLOW}Skipped:${NC}        ${TESTS_SKIPPED}"
echo -e "  ${YELLOW}Warnings:${NC}       ${WARNINGS}"
echo ""

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}  All tests passed! System is healthy.${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}  ${TESTS_FAILED} test(s) failed! Review the output above.${NC}"
    exit 1
fi
