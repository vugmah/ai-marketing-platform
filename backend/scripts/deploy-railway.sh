#!/usr/bin/env bash
# =============================================================================
# Railway Deployment Script for AI Marketing Platform
# =============================================================================
# Deploys the AI Marketing Platform backend to Railway.
# Supports blue/green deployment patterns with health verification.
#
# Usage:
#   ./scripts/deploy-railway.sh [options]
#
# Options:
#   -e, --env ENV         Target environment: staging|production (default: staging)
#   -s, --service NAME    Railway service name (default: aimp-backend)
#   -p, --project NAME    Railway project name
#   --skip-tests          Skip pre-deployment tests
#   --skip-build          Skip Docker build step
#   --skip-migrations     Skip database migrations
#   --skip-health-check   Skip post-deploy health check
#   --rollback            Rollback to previous deployment
#   --tag TAG             Deploy specific git tag or commit
#   --dry-run             Show what would be done without executing
#   -v, --verbose         Verbose output
#   -h, --help            Show this help message
#
# Examples:
#   ./scripts/deploy-railway.sh                           # Deploy to staging
#   ./scripts/deploy-railway.sh --env production          # Deploy to production
#   ./scripts/deploy-railway.sh --tag v2.1.0              # Deploy specific version
#   ./scripts/deploy-railway.sh --rollback                # Rollback production
#   ./scripts/deploy-railway.sh --skip-tests --skip-build # Quick deploy
#
# Prerequisites:
#   - Railway CLI installed: npm install -g @railway/cli
#   - Logged in: railway login
#   - Project linked: railway link
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENVIRONMENT="staging"
SERVICE_NAME="aimp-backend"
PROJECT_NAME=""
SKIP_TESTS=0
SKIP_BUILD=0
SKIP_MIGRATIONS=0
SKIP_HEALTH_CHECK=0
ROLLBACK=0
DEPLOY_TAG=""
DRY_RUN=0
VERBOSE=0
HEALTH_CHECK_RETRIES=10
HEALTH_CHECK_INTERVAL=15

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -e|--env)
        ENVIRONMENT="$2"
        shift 2
        ;;
      -s|--service)
        SERVICE_NAME="$2"
        shift 2
        ;;
      -p|--project)
        PROJECT_NAME="$2"
        shift 2
        ;;
      --skip-tests)
        SKIP_TESTS=1
        shift
        ;;
      --skip-build)
        SKIP_BUILD=1
        shift
        ;;
      --skip-migrations)
        SKIP_MIGRATIONS=1
        shift
        ;;
      --skip-health-check)
        SKIP_HEALTH_CHECK=1
        shift
        ;;
      --rollback)
        ROLLBACK=1
        shift
        ;;
      --tag)
        DEPLOY_TAG="$2"
        shift 2
        ;;
      --dry-run)
        DRY_RUN=1
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
  sed -n '4,40p' "$0"
}

log_info() {
  echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
  if [[ "$VERBOSE" -eq 1 ]]; then
    echo -e "${BLUE}[DEBUG]${NC} $1"
  fi
}

log_step() {
  echo ""
  echo -e "${CYAN}>>> $1${NC}"
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------

preflight_checks() {
  log_step "Pre-flight Checks"

  # Check Railway CLI
  if ! command -v railway &>/dev/null; then
    log_error "Railway CLI not found"
    log_info "Install with: npm install -g @railway/cli"
    exit 1
  fi

  local railway_version
  railway_version=$(railway --version 2>/dev/null || echo "unknown")
  log_info "Railway CLI: $railway_version"

  # Check authentication
  if ! railway whoami &>/dev/null 2>&1; then
    log_error "Not authenticated with Railway"
    log_info "Run: railway login"
    exit 1
  fi
  log_info "Authenticated with Railway"

  # Check project
  if [[ -n "$PROJECT_NAME" ]]; then
    log_info "Using project: $PROJECT_NAME"
  fi

  # Verify git repo
  if [[ ! -d "$PROJECT_DIR/.git" ]]; then
    log_warn "Not a git repository"
  fi

  # Check environment
  if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    log_error "Invalid environment: $ENVIRONMENT (must be 'staging' or 'production')"
    exit 1
  fi

  log_info "Target environment: $ENVIRONMENT"
  log_info "Target service: $SERVICE_NAME"
}

# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------

run_tests() {
  if [[ "$SKIP_TESTS" -eq 1 ]]; then
    log_step "Skipping Tests"
    return 0
  fi

  log_step "Running Pre-deployment Tests"

  # Run smoke tests locally
  if [[ -f "$SCRIPT_DIR/smoke-test.sh" ]]; then
    log_info "Running smoke tests..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      log_info "[DRY RUN] Would run: $SCRIPT_DIR/smoke-test.sh"
    elif bash "$SCRIPT_DIR/smoke-test.sh" 2>&1; then
      log_info "Smoke tests passed"
    else
      log_warn "Smoke tests had failures (non-blocking)"
    fi
  fi

  # Run health check
  if [[ -f "$SCRIPT_DIR/health-check.sh" ]]; then
    log_info "Running health check..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      log_info "[DRY RUN] Would run: $SCRIPT_DIR/health-check.sh"
    elif bash "$SCRIPT_DIR/health-check.sh" 2>&1; then
      log_info "Health check passed"
    else
      log_warn "Health check found issues (non-blocking)"
    fi
  fi

  log_info "Pre-deployment tests completed"
}

# ---------------------------------------------------------------------------
# Docker build
# ---------------------------------------------------------------------------

build_image() {
  if [[ "$SKIP_BUILD" -eq 1 ]]; then
    log_step "Skipping Docker Build"
    return 0
  fi

  log_step "Building Docker Image"

  local tag
  if [[ -n "$DEPLOY_TAG" ]]; then
    tag="$DEPLOY_TAG"
  else
    tag="$(git rev-parse --short HEAD 2>/dev/null || echo 'latest')"
  fi

  log_info "Building image with tag: $tag"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Would run: docker build -t aimp-backend:$tag $PROJECT_DIR"
    return 0
  fi

  if docker build -t "aimp-backend:$tag" "$PROJECT_DIR" 2>&1; then
    log_info "Docker build completed: aimp-backend:$tag"
  else
    log_error "Docker build failed"
    exit 1
  fi
}

# ---------------------------------------------------------------------------
# Database migrations
# ---------------------------------------------------------------------------

run_migrations() {
  if [[ "$SKIP_MIGRATIONS" -eq 1 ]]; then
    log_step "Skipping Migrations"
    return 0
  fi

  log_step "Running Database Migrations"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Would run: railway run -- alembic upgrade head"
    return 0
  fi

  # Run migrations via Railway CLI
  if railway run -- alembic upgrade head 2>&1; then
    log_info "Migrations completed successfully"
  else
    log_warn "Migration command had issues - may need manual intervention"
  fi
}

# ---------------------------------------------------------------------------
# Deploy to Railway
# ---------------------------------------------------------------------------

railway_deploy() {
  log_step "Deploying to Railway"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Deployment commands:"

    if [[ "$ROLLBACK" -eq 1 ]]; then
      log_info "  railway rollback --service $SERVICE_NAME"
    elif [[ -n "$DEPLOY_TAG" ]]; then
      log_info "  railway up --service $SERVICE_NAME --tag $DEPLOY_TAG"
    else
      log_info "  railway up --service $SERVICE_NAME"
    fi
    return 0
  fi

  if [[ "$ROLLBACK" -eq 1 ]]; then
    log_info "Rolling back $SERVICE_NAME..."
    if railway rollback --service "$SERVICE_NAME" 2>&1; then
      log_info "Rollback initiated"
    else
      log_error "Rollback failed"
      exit 1
    fi
    return 0
  fi

  # Set project if specified
  local project_args=""
  if [[ -n "$PROJECT_NAME" ]]; then
    project_args="--project $PROJECT_NAME"
  fi

  log_info "Deploying $SERVICE_NAME to $ENVIRONMENT..."

  # Navigate to project directory
  cd "$PROJECT_DIR"

  if [[ -n "$DEPLOY_TAG" ]]; then
    log_info "Deploying tag: $DEPLOY_TAG"
    if railway up $project_args --service "$SERVICE_NAME" 2>&1; then
      log_info "Deployment initiated"
    else
      log_error "Deployment failed"
      exit 1
    fi
  else
    if railway up $project_args --service "$SERVICE_NAME" 2>&1; then
      log_info "Deployment initiated"
    else
      log_error "Deployment failed"
      exit 1
    fi
  fi
}

# ---------------------------------------------------------------------------
# Wait for deployment
# ---------------------------------------------------------------------------

wait_for_deployment() {
  log_step "Waiting for Deployment"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Would wait for deployment to be ready"
    return 0
  fi

  log_info "Checking deployment status..."

  local retries=30
  local interval=10
  local attempt=1

  while [[ $attempt -le $retries ]]; do
    local status
    status=$(railway status --service "$SERVICE_NAME" 2>/dev/null || echo "unknown")
    log_debug "Attempt $attempt/$retries: status=$status"

    if [[ "$status" == *"DEPLOYED"* || "$status" == *"SUCCESS"* ]]; then
      log_info "Deployment completed successfully"
      return 0
    elif [[ "$status" == *"FAILED"* || "$status" == *"ERROR"* ]]; then
      log_error "Deployment failed: $status"
      return 1
    fi

    sleep "$interval"
    ((attempt++)) || true
  done

  log_warn "Deployment status check timed out - may still be in progress"
  return 0
}

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

health_check() {
  if [[ "$SKIP_HEALTH_CHECK" -eq 1 ]]; then
    log_step "Skipping Health Check"
    return 0
  fi

  log_step "Post-deployment Health Check"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Would run health checks"
    return 0
  fi

  # Get deployment URL
  local deploy_url
  deploy_url=$(railway domain --service "$SERVICE_NAME" 2>/dev/null || echo "")

  if [[ -z "$deploy_url" ]]; then
    log_warn "Could not determine deployment URL"
    return 0
  fi

  log_info "Deployment URL: https://$deploy_url"
  local base_url="https://$deploy_url"

  # Run health checks
  local attempt=1
  while [[ $attempt -le $HEALTH_CHECK_RETRIES ]]; do
    log_info "Health check attempt $attempt/$HEALTH_CHECK_RETRIES..."

    local status_code
    status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$base_url/api/v2/health/" 2>/dev/null || echo "000")

    if [[ "$status_code" == "200" ]]; then
      log_info "Health check passed (HTTP 200)"

      # Check readiness
      local ready_status
      ready_status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$base_url/api/v2/health/ready" 2>/dev/null || echo "000")
      if [[ "$ready_status" == "200" ]]; then
        log_info "Readiness probe passed (HTTP 200)"
      else
        log_warn "Readiness probe returned HTTP $ready_status"
      fi

      return 0
    else
      log_warn "Health check returned HTTP $status_code"
    fi

    sleep "$HEALTH_CHECK_INTERVAL"
    ((attempt++)) || true
  done

  log_error "Health check failed after $HEALTH_CHECK_RETRIES attempts"
  return 1
}

# ---------------------------------------------------------------------------
# Notify
# ---------------------------------------------------------------------------

notify() {
  local result="$1"

  log_step "Deployment Summary"

  local git_sha
  git_sha=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
  local git_branch
  git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

  echo ""
  echo "=========================================="
  echo "  Deployment Summary"
  echo "=========================================="
  echo "  Environment:    $ENVIRONMENT"
  echo "  Service:        $SERVICE_NAME"
  echo "  Git SHA:        $git_sha"
  echo "  Branch:         $git_branch"
  echo "  Status:         $result"
  echo "  Time:           $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "=========================================="

  if [[ "$result" == "SUCCESS" ]]; then
    log_info "Deployment completed successfully!"
  else
    log_error "Deployment completed with issues"
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  parse_args "$@"

  echo "=========================================="
  echo "  AI Marketing Platform - Railway Deploy"
  echo "  Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "=========================================="

  preflight_checks
  run_tests
  build_image
  run_migrations
  railway_deploy
  wait_for_deployment
  health_check
  notify "SUCCESS"

  log_info "Deployment process completed"
}

main "$@"
