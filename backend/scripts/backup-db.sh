#!/usr/bin/env bash
# =============================================================================
# Database Backup Script for AI Marketing Platform
# =============================================================================
# Creates compressed MySQL dumps with timestamp-based filenames.
# Supports local Docker and Railway environments.
#
# Usage:
#   ./scripts/backup-db.sh [options]
#
# Options:
#   -o, --output DIR      Output directory (default: ./backups)
#   -e, --env FILE        Environment file (default: .env)
#   --docker              Use Docker container for mysqldump
#   --railway             Use Railway CLI for backup
#   --retention DAYS      Keep backups for N days (default: 30)
#   --s3-bucket BUCKET    Upload to S3 bucket after backup
#   --dry-run             Show what would be done without executing
#   -h, --help            Show this help message
#
# Examples:
#   ./scripts/backup-db.sh
#   ./scripts/backup-db.sh --docker --output /var/backups/aimp
#   ./scripts/backup-db.sh --railway --s3-bucket my-backup-bucket
#   ./scripts/backup-db.sh --retention 7 --dry-run
#
# Environment variables:
#   DATABASE_URL          - Full database URL
#   MYSQLHOST             - MySQL host
#   MYSQLPORT             - MySQL port
#   MYSQLUSER             - MySQL user
#   MYSQLPASSWORD         - MySQL password
#   MYSQLDATABASE         - MySQL database name
#   BACKUP_RETENTION_DAYS - Backup retention period
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/backups"
ENV_FILE="$PROJECT_DIR/.env"
USE_DOCKER=0
USE_RAILWAY=0
RETENTION_DAYS=30
S3_BUCKET=""
DRY_RUN=0
COMPRESSION="gzip"
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
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -o|--output)
        OUTPUT_DIR="$2"
        shift 2
        ;;
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
      --retention)
        RETENTION_DAYS="$2"
        shift 2
        ;;
      --s3-bucket)
        S3_BUCKET="$2"
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
  sed -n '4,32p' "$0"
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

  # Priority: explicit env vars > .env > defaults
  DB_HOST="${MYSQLHOST:-localhost}"
  DB_PORT="${MYSQLPORT:-3306}"
  DB_USER="${MYSQLUSER:-root}"
  DB_PASS="${MYSQLPASSWORD:-}"
  DB_NAME="${MYSQLDATABASE:-ai_marketing}"

  # Parse DATABASE_URL if available
  if [[ -n "${DATABASE_URL:-}" ]]; then
    log_debug "Parsing DATABASE_URL"
    # Handle mysql+aiomysql:// URLs
    local url="${DATABASE_URL#mysql+aiomysql://}"
    url="${url#mysql://}"
    # Extract user:pass@host:port/dbname
    local creds_host="${url%%@*}"
    local host_db="${url#*@}"

    DB_USER="${creds_host%%:*}"
    DB_PASS="${creds_host#*:}"

    local host_port_db="${host_db%%/*}"
    DB_NAME="${host_db#*/}"
    DB_NAME="${DB_NAME%%\?*}"

    DB_HOST="${host_port_db%%:*}"
    local port_part="${host_port_db#*:}"
    if [[ "$port_part" != "$host_port_db" ]]; then
      DB_PORT="$port_part"
    fi
  fi

  log_debug "DB_HOST=$DB_HOST, DB_PORT=$DB_PORT, DB_USER=$DB_USER, DB_NAME=$DB_NAME"
}

# ---------------------------------------------------------------------------
# Backup functions
# ---------------------------------------------------------------------------

backup_local() {
  local timestamp
  timestamp=$(date -u +%Y%m%d_%H%M%S)
  local filename="aimp_backup_${timestamp}.sql"
  local filepath="$OUTPUT_DIR/$filename"
  local compressed_path="${filepath}.gz"

  mkdir -p "$OUTPUT_DIR"

  log_info "Starting backup: $filename"
  log_info "Database: $DB_NAME on $DB_HOST:$DB_PORT"

  local mysqldump_cmd
  if [[ "$USE_DOCKER" -eq 1 ]]; then
    mysqldump_cmd="docker exec aimp_mysql mysqldump -h localhost -u $DB_USER -p'$DB_PASS' $DB_NAME"
  else
    mysqldump_cmd="mysqldump -h $DB_HOST -P $DB_PORT -u $DB_USER -p'$DB_PASS' $DB_NAME"
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Would execute: $mysqldump_cmd | gzip > $compressed_path"
    return 0
  fi

  # Run mysqldump with compression
  if eval "$mysqldump_cmd" 2>/dev/null | gzip > "$compressed_path"; then
    local size
    size=$(du -h "$compressed_path" | cut -f1)
    log_info "Backup completed: $compressed_path ($size)"

    # Verify backup integrity
    if gunzip -t "$compressed_path" 2>/dev/null; then
      log_info "Backup integrity verified"
    else
      log_error "Backup file is corrupted!"
      return 1
    fi

    # Upload to S3 if configured
    if [[ -n "$S3_BUCKET" ]]; then
      upload_to_s3 "$compressed_path"
    fi

    echo "$compressed_path"
    return 0
  else
    log_error "Backup failed!"
    rm -f "$compressed_path"
    return 1
  fi
}

backup_railway() {
  if ! command -v railway &>/dev/null; then
    log_error "Railway CLI not found. Install with: npm install -g @railway/cli"
    return 1
  fi

  local timestamp
  timestamp=$(date -u +%Y%m%d_%H%M%S)
  local filename="aimp_backup_railway_${timestamp}.sql.gz"
  local filepath="$OUTPUT_DIR/$filename"

  mkdir -p "$OUTPUT_DIR"

  log_info "Starting Railway backup: $filename"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Would execute: railway connect mysql && mysqldump ..."
    return 0
  fi

  # Use Railway CLI to connect and dump
  if railway connect mysql -- mysqldump -u root --all-databases 2>/dev/null | gzip > "$filepath"; then
    local size
    size=$(du -h "$filepath" | cut -f1)
    log_info "Railway backup completed: $filepath ($size)"

    if [[ -n "$S3_BUCKET" ]]; then
      upload_to_s3 "$filepath"
    fi

    echo "$filepath"
    return 0
  else
    log_error "Railway backup failed!"
    return 1
  fi
}

upload_to_s3() {
  local file="$1"

  if ! command -v aws &>/dev/null; then
    log_warn "AWS CLI not found, skipping S3 upload"
    return 1
  fi

  local s3_key="backups/aimp/$(basename "$file")"
  log_info "Uploading to s3://$S3_BUCKET/$s3_key"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Would upload to S3"
    return 0
  fi

  if aws s3 cp "$file" "s3://$S3_BUCKET/$s3_key"; then
    log_info "Upload completed"
  else
    log_error "Upload failed"
    return 1
  fi
}

cleanup_old_backups() {
  if [[ ! -d "$OUTPUT_DIR" ]]; then
    return 0
  fi

  log_info "Cleaning up backups older than $RETENTION_DAYS days"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    log_info "[DRY RUN] Would delete:"
    find "$OUTPUT_DIR" -name "aimp_backup_*.sql.gz" -type f -mtime +"$RETENTION_DAYS" -print || true
    return 0
  fi

  local deleted=0
  while IFS= read -r file; do
    rm -f "$file"
    log_info "Deleted old backup: $file"
    ((deleted++)) || true
  done < <(find "$OUTPUT_DIR" -name "aimp_backup_*.sql.gz" -type f -mtime +"$RETENTION_DAYS" 2>/dev/null || true)

  log_info "Deleted $deleted old backup(s)"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

main() {
  parse_args "$@"
  load_env

  echo "=========================================="
  echo "  AI Marketing Platform - Database Backup"
  echo "  Time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "  Output: $OUTPUT_DIR"
  echo "  Retention: $RETENTION_DAYS days"
  echo "=========================================="

  if [[ "$USE_RAILWAY" -eq 1 ]]; then
    backup_railway
  else
    backup_local
  fi

  cleanup_old_backups

  log_info "Backup process completed"
}

main "$@"
