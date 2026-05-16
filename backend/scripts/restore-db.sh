#!/usr/bin/env bash
# =============================================================================
# Database Restore Script for AI Marketing Platform
# =============================================================================
# Restores a MySQL database from a compressed backup file.
# Supports local Docker and Railway environments.
#
# Usage:
#   ./scripts/restore-db.sh <backup_file> [options]
#
# Arguments:
#   backup_file           Path to the .sql.gz backup file to restore
#
# Options:
#   -e, --env FILE        Environment file (default: .env)
#   --docker              Restore into Docker container
#   --railway             Restore via Railway CLI
#   --database NAME       Target database name (overrides env)
#   --force               Skip confirmation prompt
#   --dry-run             Show what would be done without executing
#   -h, --help            Show this help message
#
# Examples:
#   ./scripts/restore-db.sh backups/aimp_backup_20240115_120000.sql.gz
#   ./scripts/restore-db.sh backups/aimp_backup_20240115_120000.sql.gz --docker --force
#   ./scripts/restore-db.sh backups/aimp_backup_20240115_120000.sql.gz --railway
#
# WARNING:
#   This will DROP and recreate the target database. All existing data
#   will be lost. Use with caution in production!
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_DIR/.env"
USE_DOCKER=0
USE_RAILWAY=0
TARGET_DB=""
FORCE=0
DRY_RUN=0
VERBOSE=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------

parse_args() {
  if [[ $# -eq 0 ]]; then
    show_help
    exit 1
  fi

  # First argument must be the backup file
  BACKUP_FILE="${1:-}"
  shift || true

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -e|--env)
        ENV_FILE="$2"
        shift 2
        ;;
      --docker)
        USE_DOCKER=1
        shift
        ;;
      --railway)
        USE_RAILWAY=1
        shift
        ;;
      --database)
        TARGET_DB="$2"
        shift 2
        ;;
      --force)
        FORCE=1
        shift
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
  sed -n '4,38p' "$0"
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

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------

load_env() {
  if [[ -f "$ENV_FILE" ]]; then
    log_debug "Loading env from $ENV_FILE"
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
  fi

  DB_HOST="${MYSQLHOST:-localhost}"
  DB_PORT="${MYSQLPORT:-3306}"
  DB_USER="${MYSQLUSER:-root}"
  DB_PASS="${MYSQLPASSWORD:-}"
  DB_NAME="${TARGET_DB:-${MYSQLDATABASE:-ai_marketing}}"

  # Parse DATABASE_URL if available
  if [[ -n "${DATABASE_URL:-}" && -z "${TARGET_DB}" ]]; then
    log_debug "Parsing DATABASE_URL"
    local url="${DATABASE_URL#mysql+aiomysql://}"
    url="${url#mysql://}"
    local creds_host="${url%%@*}"
    local host_db="${url#*@}"

    DB_USER="${creds_host%%:*}"
    DB_PASS="${creds_host#*:}"

    local host_port_db="${host_db%%/*}"
    local db_from_url="${host_db#*/}"
    DB_NAME="${db_from_url%%\?*}"

    DB_HOST="${host_port_db%%:*}"
    local port_part="${host_port_db#*:}"
    if [[ "$port_part" != "$host_port_db" ]]; then
      DB_PORT="$port_part"
    fi
  fi

  log_debug "DB_HOST=$DB_HOST, DB_PORT=$DB_PORT, DB_USER=$DB_USER, DB_NAME=$DB_NAME"
}

# ---------------------------------------------------------------------------
# Restore functions
# ---------------------------------------------------------------------------

verify_backup() {
  local file="$1"

  if [[ ! -f "$file" ]]; then
    log_error "Backup file not found: $file"
    return 1
  fi

  log_info "Verifying backup file: $file"
  local size
  size=$(du -h "$file" | cut -f1)
  log_info "Backup size: $size"

  # Check if it's a valid gzip file
  if [[ "$file" == *.gz ]]; then
    if gunzip -t "$file" 2>/dev/null; then
      log_info "Backup file is a valid gzip archive"
    else
      log_error "Backup file is not a valid gzip archive!"
      return 1
    fi
  fi

  # Check if backup contains SQL
  if [[ "$file" == *.gz ]]; then
    if zgrep -q "CREATE TABLE\|INSERT INTO\|DROP TABLE" "$file" 2>/dev/null; then
      log_info "Backup contains valid SQL statements"
    else
      log_warn "Backup may not contain valid SQL - proceed with caution"
    fi
  fi

  return 0
}

confirm_restore() {
  if [[ "$FORCE" -eq 1 ]]; then
    return 0
  fi

  echo ""
  echo -e "${YELLOW}WARNING: This will DESTROY all existing data in database '$DB_NAME'${NC}"
  echo -e "${YELLOW}         and replace it with data from:$NC"
  echo -e "${YELLOW}         $BACKUP_FILE${NC}"
  echo ""
  echo -n "Are you sure you want to continue? [y/N]: "
  read -r response

  if [[ "$response" =~ ^[Yy]$ ]]; then
    return 0
  else
    log_info "Restore cancelled by user"
    return 1
  fi
}

restore_local() {
  log_info "Starting restore to database: $DB_NAME"
  log_info "Source: $BACKUP_FILE"

  local mysql_cmd
  if [[ "$USE_DOCKER" -eq 1 ]]; then
    mysql_cmd="docker exec -i aimp_mysql mysql -h localhost -u $DB_USER -p'$DB_PASS'"
  else
    mysql_cmd="mysql -h $DB_HOST -P $DB_PORT -u $DB_USER -p'$DB_PASS'"
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Would execute restore pipeline"
    log_info "[DRY RUN] gunzip < $BACKUP_FILE | $mysql_cmd $DB_NAME"
    return 0
  fi

  # Create database if it doesn't exist
  log_info "Creating database (if not exists)..."
  eval "$mysql_cmd -e 'CREATE DATABASE IF NOT EXISTS \`$DB_NAME\`; USE \`$DB_NAME\`;'" 2>/dev/null || true

  # Restore from backup
  log_info "Restoring data..."
  if gunzip < "$BACKUP_FILE" | eval "$mysql_cmd $DB_NAME"; then
    log_info "Restore completed successfully"
  else
    log_error "Restore failed!"
    return 1
  fi

  # Verify restore
  local table_count
  table_count=$(eval "$mysql_cmd $DB_NAME -e 'SHOW TABLES;' 2>/dev/null" | wc -l)
  table_count=$((table_count - 1))  # Subtract header line
  log_info "Restored database contains $table_count tables"

  return 0
}

restore_railway() {
  if ! command -v railway &>/dev/null; then
    log_error "Railway CLI not found. Install with: npm install -g @railway/cli"
    return 1
  fi

  log_info "Starting Railway restore to database: $DB_NAME"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Would execute: railway connect mysql"
    return 0
  fi

  log_info "Restore via Railway..."
  if gunzip < "$BACKUP_FILE" | railway connect mysql -- mysql -u root; then
    log_info "Railway restore completed successfully"
  else
    log_error "Railway restore failed!"
    return 1
  fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  parse_args "$@"
  load_env

  echo "=========================================="
  echo "  AI Marketing Platform - Database Restore"
  echo "  Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "=========================================="

  # Verify backup file
  verify_backup "$BACKUP_FILE"

  # Get confirmation
  confirm_restore || exit 0

  # Perform restore
  if [[ "$USE_RAILWAY" -eq 1 ]]; then
    restore_railway
  else
    restore_local
  fi

  log_info "Restore process completed"
}

main "$@"
