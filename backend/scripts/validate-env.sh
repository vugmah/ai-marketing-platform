#!/usr/bin/env bash
# =============================================================================
# Environment Variable Validation Script
# =============================================================================
# Validates all required and optional environment variables for the
# AI Marketing Platform. Checks connectivity to configured services.
#
# Usage:
#   ./scripts/validate-env.sh [options]
#
# Options:
#   -e, --env FILE        Environment file to load (default: .env)
#   --check-connectivity  Test connectivity to DB and Redis
#   --railway             Validate Railway-specific variables
#   --strict              Exit with error on warnings
#   -v, --verbose         Show all variables, not just issues
#   -h, --help            Show this help message
#
# Examples:
#   ./scripts/validate-env.sh
#   ./scripts/validate-env.sh --env .env.production
#   ./scripts/validate-env.sh --check-connectivity --strict
#   ./scripts/validate-env.sh --railway
#
# Exit codes:
#   0 - All validations passed
#   1 - Required variables missing or invalid
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
CHECK_CONNECTIVITY=0
RAILWAY_MODE=0
STRICT=0
VERBOSE=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Counters
VALID=0
MISSING=0
WARNINGS=0
ERRORS=0

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -e|--env)
        ENV_FILE="$2"
        shift 2
        ;;
      --check-connectivity)
        CHECK_CONNECTIVITY=1
        shift
        ;;
      --railway)
        RAILWAY_MODE=1
        shift
        ;;
      --strict)
        STRICT=1
        shift
        ;;
      -v|--verbose)
        VERBOSE=1
        shift
        ;;
      -h|--help)
        show_help
        exit 0
        ;;
      *)
        echo "Unknown option: $1"
        show_help
        exit 1
        ;;
    esac
  done
}

show_help() {
  sed -n '4,30p' "$0"
}

log_ok() {
  echo -e "${GREEN}  [OK]${NC} $1"
}

log_missing() {
  echo -e "${RED}  [MISSING]${NC} $1"
  ((MISSING++)) || true
}

log_warning() {
  echo -e "${YELLOW}  [WARN]${NC} $1"
  ((WARNINGS++)) || true
}

log_error() {
  echo -e "${RED}  [ERROR]${NC} $1"
  ((ERRORS++)) || true
}

log_info() {
  if [[ "$VERBOSE" -eq 1 ]]; then
    echo -e "${BLUE}  [INFO]${NC} $1"
  fi
}

# ---------------------------------------------------------------------------
# Variable checks
# ---------------------------------------------------------------------------

check_required() {
  local name="$1"
  local value="${!name:-}"

  if [[ -n "$value" ]]; then
    log_info "$name=$value"
    ((VALID++)) || true
  else
    log_missing "Required variable $name is not set"
  fi
}

check_optional() {
  local name="$1"
  local default="${2:-}"
  local value="${!name:-}"

  if [[ -n "$value" ]]; then
    log_info "$name=$value (set)"
    ((VALID++)) || true
  else
    log_info "$name not set (will use default: $default)"
  fi
}

check_secret() {
  local name="$1"
  local value="${!name:-}"

  if [[ -n "$value" ]]; then
    local masked="${value:0:4}****"
    log_info "$name=$masked (set)"
    ((VALID++)) || true
  else
    log_missing "Secret variable $name is not set"
  fi
}

check_url() {
  local name="$1"
  local value="${!name:-}"
  local protocol="${2:-}"

  if [[ -z "$value" ]]; then
    log_missing "URL variable $name is not set"
    return
  fi

  if [[ -n "$protocol" && ! "$value" == "$protocol"* ]]; then
    log_warning "$name should use $protocol protocol (got: $value)"
    return
  fi

  log_info "$name=$value"
  ((VALID++)) || true
}

# ---------------------------------------------------------------------------
# Connectivity tests
# ---------------------------------------------------------------------------

test_db_connectivity() {
  echo ""
  echo -e "${CYAN}Database Connectivity${NC}"

  local host="${MYSQLHOST:-localhost}"
  local port="${MYSQLPORT:-3306}"

  if command -v nc &>/dev/null; then
    if nc -z "$host" "$port" -w 3 2>/dev/null; then
      log_ok "MySQL ($host:$port) is reachable"
    else
      log_error "MySQL ($host:$port) is NOT reachable"
    fi
  elif command -v mysql &>/dev/null; then
    if mysql -h "$host" -P "$port" -u "${MYSQLUSER:-root}" -p"${MYSQLPASSWORD:-}" -e "SELECT 1" &>/dev/null; then
      log_ok "MySQL connection successful"
    else
      log_error "MySQL connection failed"
    fi
  else
    log_warning "Neither nc nor mysql client available for connectivity test"
  fi
}

test_redis_connectivity() {
  echo ""
  echo -e "${CYAN}Redis Connectivity${NC}"

  local redis_url="${REDIS_URL:-redis://localhost:6379}"

  # Extract host and port from Redis URL
  local host port
  host=$(echo "$redis_url" | sed -E 's|redis://([^:]+):.*|\1|')
  port=$(echo "$redis_url" | sed -E 's|redis://[^:]+:([0-9]+).*|\1|')

  if [[ -z "$port" || "$port" == "$redis_url" ]]; then
    port=6379
  fi

  if command -v redis-cli &>/dev/null; then
    if redis-cli -h "$host" -p "$port" ping 2>/dev/null | grep -q "PONG"; then
      log_ok "Redis ($host:$port) is reachable and responding"
    else
      log_error "Redis ($host:$port) is NOT reachable"
    fi
  elif command -v nc &>/dev/null; then
    if nc -z "$host" "$port" -w 3 2>/dev/null; then
      log_ok "Redis ($host:$port) port is open"
    else
      log_error "Redis ($host:$port) port is NOT open"
    fi
  else
    log_warning "Neither redis-cli nor nc available for connectivity test"
  fi
}

# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

validate() {
  echo ""
  echo -e "${CYAN}Required Variables${NC}"

  # Application
  check_required "APP_NAME"
  check_secret "SECRET_KEY"
  check_secret "JWT_SECRET_KEY"

  # Database
  if [[ -z "${DATABASE_URL:-}" ]]; then
    check_required "MYSQLHOST"
    check_required "MYSQLPORT"
    check_required "MYSQLUSER"
    check_secret "MYSQLPASSWORD"
    check_required "MYSQLDATABASE"
  else
    check_url "DATABASE_URL" "mysql+aiomysql://"
  fi

  # Redis
  if [[ -z "${REDIS_URL:-}" ]]; then
    log_warning "REDIS_URL not set, will use default redis://localhost:6379/0"
  else
    check_url "REDIS_URL" "redis://"
  fi

  # Celery
  check_url "CELERY_BROKER_URL"
  check_optional "CELERY_RESULT_BACKEND"

  echo ""
  echo -e "${CYAN}Optional Variables${NC}"

  check_optional "DEBUG" "False"
  check_optional "LOG_LEVEL" "INFO"
  check_optional "ENVIRONMENT" "development"

  # External API keys
  check_optional "OPENAI_API_KEY"
  check_optional "META_APP_ID"
  check_optional "META_APP_SECRET"
  check_optional "GOOGLE_ADS_DEVELOPER_TOKEN"
  check_optional "SENTRY_DSN"

  # Email
  check_optional "SMTP_HOST"
  check_optional "SMTP_PORT"
  check_optional "SMTP_USER"
  check_optional "SMTP_PASSWORD"

  # Storage
  check_optional "S3_BUCKET"
  check_optional "AWS_ACCESS_KEY_ID"
  check_optional "AWS_SECRET_ACCESS_KEY"
  check_optional "AWS_REGION"

  echo ""
  echo -e "${CYAN}Validation${NC}"

  # Validate JWT configuration
  if [[ -n "${JWT_SECRET_KEY:-}" ]]; then
    local jwt_len
    jwt_len=${#JWT_SECRET_KEY}
    if [[ $jwt_len -lt 32 ]]; then
      log_warning "JWT_SECRET_KEY is only ${jwt_len} chars (recommended: 32+ chars)"
    else
      log_ok "JWT_SECRET_KEY length: ${jwt_len} chars"
    fi
  fi

  # Validate SECRET_KEY
  if [[ -n "${SECRET_KEY:-}" ]]; then
    local secret_len
    secret_len=${#SECRET_KEY}
    if [[ $secret_len -lt 32 ]]; then
      log_warning "SECRET_KEY is only ${secret_len} chars (recommended: 32+ chars)"
    else
      log_ok "SECRET_KEY length: ${secret_len} chars"
    fi
  fi

  # Check for default/placeholder values
  if [[ "${JWT_SECRET_KEY:-}" == "super-secret-jwt-key-change-in-production" ]]; then
    log_warning "JWT_SECRET_KEY is using the default value - change in production!"
  fi

  if [[ "${SECRET_KEY:-}" == "super-secret-encryption-key-change-in-production" ]]; then
    log_warning "SECRET_KEY is using the default value - change in production!"
  fi
}

validate_railway() {
  echo ""
  echo -e "${CYAN}Railway-Specific Variables${NC}"

  # Check Railway-specific env vars
  check_optional "RAILWAY_ENVIRONMENT"
  check_optional "RAILWAY_SERVICE_NAME"
  check_optional "RAILWAY_PROJECT_NAME"
  check_optional "RAILWAY_STATIC_URL"

  # Railway auto-provides these
  if [[ -n "${RAILWAY_ENVIRONMENT:-}" ]]; then
    log_ok "Running in Railway environment: $RAILWAY_ENVIRONMENT"
  fi

  # MySQL on Railway
  if [[ -n "${MYSQL_URL:-}" ]]; then
    log_ok "Railway MySQL URL is configured"
  elif [[ -n "${MYSQLHOST:-}" ]]; then
    log_ok "Railway MySQL individual variables are set"
  else
    log_warning "No Railway MySQL configuration detected"
  fi

  # Redis on Railway
  if [[ -n "${REDIS_URL:-}" || -n "${REDIS_PUBLIC_URL:-}" ]]; then
    log_ok "Railway Redis URL is configured"
  else
    log_warning "No Railway Redis configuration detected"
  fi

  # Volume for Railway
  if [[ -n "${RAILWAY_VOLUME_MOUNT_PATH:-}" ]]; then
    log_ok "Railway volume is mounted at: $RAILWAY_VOLUME_MOUNT_PATH"
  else
    log_info "No Railway volume configured"
  fi
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

main() {
  parse_args "$@"

  # Load .env file if it exists
  if [[ -f "$ENV_FILE" ]]; then
    echo "Loading environment from: $ENV_FILE"
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
  fi

  echo "=========================================="
  echo "  AI Marketing Platform - Env Validation"
  echo "  Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "  File: $ENV_FILE"
  echo "=========================================="

  # Run validations
  validate

  if [[ "$RAILWAY_MODE" -eq 1 ]]; then
    validate_railway
  fi

  if [[ "$CHECK_CONNECTIVITY" -eq 1 ]]; then
    test_db_connectivity
    test_redis_connectivity
  fi

  # Summary
  echo ""
  echo "=========================================="
  echo "  Validation Summary"
  echo "=========================================="
  echo "  Valid:   $VALID"
  echo "  Missing: $MISSING"
  echo "  Warnings: $WARNINGS"
  echo "  Errors:  $ERRORS"
  echo "=========================================="

  if [[ $MISSING -gt 0 ]]; then
    echo -e "${RED}RESULT: FAILED - $MISSING required variable(s) missing${NC}"
    exit 1
  fi

  if [[ $ERRORS -gt 0 ]]; then
    echo -e "${RED}RESULT: FAILED - $ERRORS error(s) found${NC}"
    exit 1
  fi

  if [[ $WARNINGS -gt 0 ]]; then
    echo -e "${YELLOW}RESULT: PASSED WITH WARNINGS${NC}"
    if [[ "$STRICT" -eq 1 ]]; then
      exit 1
    fi
    exit 0
  fi

  echo -e "${GREEN}RESULT: ALL CHECKS PASSED${NC}"
  exit 0
}

main "$@"
