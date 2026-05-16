#!/usr/bin/env bash
# =============================================================================
# Smoke Test Script for AI Marketing Platform
# =============================================================================
# Runs a suite of smoke tests against the API to verify basic functionality.
# Tests authentication, companies, campaigns, analytics, and ERP endpoints.
#
# Usage:
#   ./scripts/smoke-test.sh [base_url]
#
#   BASE_URL defaults to http://localhost:8000
#
# Environment variables:
#   TEST_EMAIL        - Test user email (default: admin@example.com)
#   TEST_PASSWORD     - Test user password (default: password123)
#   SKIP_AUTH_TESTS   - Set to 1 to skip auth-dependent tests
#   VERBOSE           - Set to 1 for verbose output
#
# Examples:
#   ./scripts/smoke-test.sh
#   ./scripts/smoke-test.sh https://api.railway.app
#   VERBOSE=1 ./scripts/smoke-test.sh
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
# =============================================================================

set -euo pipefail

# Configuration
BASE_URL="${1:-http://localhost:8000}"
TEST_EMAIL="${TEST_EMAIL:-admin@example.com}"
TEST_PASSWORD="${TEST_PASSWORD:-password123}"
SKIP_AUTH_TESTS="${SKIP_AUTH_TESTS:-0}"
VERBOSE="${VERBOSE:-0}"
TIMEOUT=10

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test tracking
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Access token storage
ACCESS_TOKEN=""
REFRESH_TOKEN=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

log_section() {
  echo ""
  echo -e "${BLUE}=== $1 ===${NC}"
}

log_pass() {
  echo -e "${GREEN}[PASS]${NC} $1"
  ((TESTS_PASSED++))
}

log_fail() {
  echo -e "${RED}[FAIL]${NC} $1"
  ((TESTS_FAILED++))
}

log_skip() {
  echo -e "${YELLOW}[SKIP]${NC} $1"
  ((TESTS_SKIPPED++))
}

api_request() {
  local method="$1"
  local path="$2"
  local data="${3:-}"
  local auth_header=""

  if [[ -n "$ACCESS_TOKEN" ]]; then
    auth_header="Authorization: Bearer $ACCESS_TOKEN"
  fi

  local url="${BASE_URL}${path}"
  local curl_opts=("-s" "-w" "\n%{http_code}" "--max-time" "$TIMEOUT")

  if [[ -n "$auth_header" ]]; then
    curl_opts+=("-H" "$auth_header")
  fi

  if [[ "$method" != "GET" && -n "$data" ]]; then
    curl_opts+=("-H" "Content-Type: application/json" "-d" "$data")
  fi

  if [[ "$VERBOSE" -eq 1 ]]; then
    echo "  -> $method $url" >&2
  fi

  local response
  response=$(curl "${curl_opts[@]}" -X "$method" "$url" 2>/dev/null || echo -e "\n000")

  local body
  local status_code
  body=$(echo "$response" | sed '$d')
  status_code=$(echo "$response" | tail -n1)

  echo -e "${status_code}\n${body}"
}

assert_status() {
  local test_name="$1"
  local expected="$2"
  local actual="$3"

  if [[ "$actual" == "$expected" ]]; then
    log_pass "$test_name (HTTP $actual)"
  else
    log_fail "$test_name (expected HTTP $expected, got $actual)"
  fi
}

assert_json_field() {
  local test_name="$1"
  local body="$2"
  local field="$3"
  local expected="$4"

  local actual
  actual=$(echo "$body" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    value = data
    for key in '$field'.split('.'):
        value = value.get(key, 'FIELD_NOT_FOUND') if isinstance(value, dict) else 'FIELD_NOT_FOUND'
    print(value)
except Exception as e:
    print('PARSE_ERROR')
" 2>/dev/null || echo "PARSE_ERROR")

  if [[ "$actual" == "$expected" ]]; then
    log_pass "$test_name ($field=$actual)"
  else
    log_fail "$test_name (expected $field='$expected', got '$actual')"
  fi
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

echo "=========================================="
echo "  AI Marketing Platform - Smoke Tests"
echo "  Target: $BASE_URL"
echo "  Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=========================================="

# ---------------------------------------------------------------------------
# Health endpoint tests
# ---------------------------------------------------------------------------

log_section "Health Endpoints"

# Test basic health
result=$(api_request "GET" "/api/v2/health/")
status=$(echo "$result" | head -n1)
body=$(echo "$result" | tail -n +2)
assert_status "Basic health check" "200" "$status"
if [[ "$status" == "200" ]]; then
  assert_json_field "Health status field" "$body" "status" "healthy"
fi

# Test liveness probe
result=$(api_request "GET" "/api/v2/health/live")
status=$(echo "$result" | head -n1)
assert_status "Liveness probe" "200" "$status"

# Test readiness probe
result=$(api_request "GET" "/api/v2/health/ready")
status=$(echo "$result" | head -n1)
if [[ "$status" == "200" || "$status" == "503" ]]; then
  log_pass "Readiness probe (HTTP $status)"
else
  log_fail "Readiness probe (unexpected HTTP $status)"
fi

# Test metrics endpoint
result=$(api_request "GET" "/api/v2/health/metrics")
status=$(echo "$result" | head -n1)
assert_status "Prometheus metrics endpoint" "200" "$status"

# Test detailed health
result=$(api_request "GET" "/api/v2/health/detailed")
status=$(echo "$result" | head -n1)
body=$(echo "$result" | tail -n +2)
assert_status "Detailed health check" "200" "$status"
if [[ "$status" == "200" ]]; then
  assert_json_field "Overall status field" "$body" "overall_status" "healthy"
fi

# Test DB health
result=$(api_request "GET" "/api/v2/health/db")
status=$(echo "$result" | head -n1)
body=$(echo "$result" | tail -n +2)
if [[ "$status" == "200" ]]; then
  assert_json_field "DB status field" "$body" "status" "healthy"
else
  log_fail "DB health check (HTTP $status)"
fi

# Test Redis health
result=$(api_request "GET" "/api/v2/health/redis")
status=$(echo "$result" | head -n1)
body=$(echo "$result" | tail -n +2)
if [[ "$status" == "200" ]]; then
  assert_json_field "Redis status field" "$body" "status" "healthy"
else
  log_fail "Redis health check (HTTP $status)"
fi

# ---------------------------------------------------------------------------
# API documentation tests
# ---------------------------------------------------------------------------

log_section "API Documentation"

result=$(api_request "GET" "/api/docs")
status=$(echo "$result" | head -n1)
assert_status "Swagger UI" "200" "$status"

result=$(api_request "GET" "/api/openapi.json")
status=$(echo "$result" | head -n1)
assert_status "OpenAPI schema" "200" "$status"

# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------

if [[ "$SKIP_AUTH_TESTS" -eq 0 ]]; then
  log_section "Authentication"

  # Register test user
  result=$(api_request "POST" "/api/v2/auth/register" "{\"email\": \"$TEST_EMAIL\", \"password\": \"$TEST_PASSWORD\", \"full_name\": \"Test User\", \"company_name\": \"Test Co\"}")
  status=$(echo "$result" | head -n1)
  body=$(echo "$result" | tail -n +2)

  if [[ "$status" == "201" || "$status" == "200" || "$status" == "409" ]]; then
    log_pass "User registration (HTTP $status)"
  else
    log_fail "User registration (HTTP $status)"
  fi

  # Login
  result=$(api_request "POST" "/api/v2/auth/login" "{\"username\": \"$TEST_EMAIL\", \"password\": \"$TEST_PASSWORD\"}")
  status=$(echo "$result" | head -n1)
  body=$(echo "$result" | tail -n +2)

  if [[ "$status" == "200" ]]; then
    log_pass "User login (HTTP $status)"
    ACCESS_TOKEN=$(echo "$body" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('access_token', ''))
" 2>/dev/null || echo "")
    REFRESH_TOKEN=$(echo "$body" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('refresh_token', ''))
" 2>/dev/null || echo "")

    if [[ -n "$ACCESS_TOKEN" ]]; then
      log_pass "Access token received"
    else
      log_fail "No access token in login response"
    fi
  else
    log_fail "User login (HTTP $status)"
    SKIP_AUTH_TESTS=1
  fi

  # Refresh token
  if [[ -n "$REFRESH_TOKEN" ]]; then
    result=$(api_request "POST" "/api/v2/auth/refresh" "{\"refresh_token\": \"$REFRESH_TOKEN\"}")
    status=$(echo "$result" | head -n1)
    assert_status "Token refresh" "200" "$status"
  fi

  # Get current user
  if [[ -n "$ACCESS_TOKEN" ]]; then
    result=$(api_request "GET" "/api/v2/auth/me")
    status=$(echo "$result" | head -n1)
    assert_status "Get current user" "200" "$status"
  fi
else
  log_section "Authentication"
  log_skip "Authentication tests (SKIP_AUTH_TESTS=1)"
fi

# ---------------------------------------------------------------------------
# Company tests
# ---------------------------------------------------------------------------

if [[ "$SKIP_AUTH_TESTS" -eq 0 && -n "$ACCESS_TOKEN" ]]; then
  log_section "Companies"

  # List companies
  result=$(api_request "GET" "/api/v2/companies/")
  status=$(echo "$result" | head -n1)
  assert_status "List companies" "200" "$status"

  # Create company
  result=$(api_request "POST" "/api/v2/companies/" "{\"name\": \"Smoke Test Company\", \"slug\": \"smoke-test\", \"website\": \"https://example.com\"}")
  status=$(echo "$result" | head -n1)
  body=$(echo "$result" | tail -n +2)

  if [[ "$status" == "201" || "$status" == "200" ]]; then
    log_pass "Create company (HTTP $status)"
    COMPANY_ID=$(echo "$body" | python3 -c "
import sys, json
print(json.load(sys.stdin).get('id', ''))
" 2>/dev/null || echo "")

    if [[ -n "$COMPANY_ID" ]]; then
      # Get company
      result=$(api_request "GET" "/api/v2/companies/${COMPANY_ID}")
      status=$(echo "$result" | head -n1)
      assert_status "Get company" "200" "$status"

      # Update company
      result=$(api_request "PUT" "/api/v2/companies/${COMPANY_ID}" "{\"name\": \"Updated Smoke Test Co\"}")
      status=$(echo "$result" | head -n1)
      assert_status "Update company" "200" "$status"

      # Delete company
      result=$(api_request "DELETE" "/api/v2/companies/${COMPANY_ID}")
      status=$(echo "$result" | head -n1)
      assert_status "Delete company" "204" "$status"
    fi
  else
    log_fail "Create company (HTTP $status)"
  fi
else
  log_section "Companies"
  log_skip "Company tests (requires auth)"
fi

# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

if [[ "$SKIP_AUTH_TESTS" -eq 0 && -n "$ACCESS_TOKEN" ]]; then
  log_section "Dashboard"

  result=$(api_request "GET" "/api/v2/dashboard/")
  status=$(echo "$result" | head -n1)
  assert_status "Dashboard overview" "200" "$status"
else
  log_section "Dashboard"
  log_skip "Dashboard tests (requires auth)"
fi

# ---------------------------------------------------------------------------
# Analytics tests
# ---------------------------------------------------------------------------

if [[ "$SKIP_AUTH_TESTS" -eq 0 && -n "$ACCESS_TOKEN" ]]; then
  log_section "Analytics"

  result=$(api_request "GET" "/api/v2/analytics/")
  status=$(echo "$result" | head -n1)
  assert_status "Analytics overview" "200" "$status"
else
  log_section "Analytics"
  log_skip "Analytics tests (requires auth)"
fi

# ---------------------------------------------------------------------------
# ERP tests
# ---------------------------------------------------------------------------

if [[ "$SKIP_AUTH_TESTS" -eq 0 && -n "$ACCESS_TOKEN" ]]; then
  log_section "ERP Integration"

  result=$(api_request "GET" "/api/v2/erp/health")
  status=$(echo "$result" | head -n1)
  assert_status "ERP health check" "200" "$status"
else
  log_section "ERP Integration"
  log_skip "ERP tests (requires auth)"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

echo ""
echo "=========================================="
echo "  Smoke Test Results"
echo "=========================================="
echo "  Passed:  $TESTS_PASSED"
echo "  Failed:  $TESTS_FAILED"
echo "  Skipped: $TESTS_SKIPPED"
echo "=========================================="

if [[ "$TESTS_FAILED" -gt 0 ]]; then
  echo -e "${RED}RESULT: FAILED${NC}"
  exit 1
else
  echo -e "${GREEN}RESULT: PASSED${NC}"
  exit 0
fi
