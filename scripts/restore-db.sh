#!/bin/bash
# =============================================================================
# AI Marketing Platform - Database Restore Script
# =============================================================================
# Restores MySQL database from S3/R2 or local backup file.
#
# Usage:
#   ./scripts/restore-db.sh s3://bucket/db-backups/2025/01/15/aimp_backup_full_20250115_120000.sql.gz
#   ./scripts/restore-db.sh local ./backups/aimp_backup_full_20250115_120000.sql.gz
#   ./scripts/restore-db.sh latest               # Restore most recent S3 backup
#   ./scripts/restore-db.sh latest-local         # Restore most recent local backup
#   ./scripts/restore-db.sh --list-s3            # List available S3 backups
#   ./scripts/restore-db.sh --list-local         # List available local backups
#
# Environment Variables Required:
#   DATABASE_URL or MYSQL_* vars - Target database connection
#   S3_BUCKET_NAME, S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY
#
# WARNING: This script DROPS the existing database before restore.
# Always verify backups before restoring to production.
#
# Exit Codes:
#   0  - Success
#   1  - Configuration error
#   2  - Download failed
#   3  - Restore failed
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
RESTORE_DIR="/tmp/aimp-restore"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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
log_info()  { echo -e "${BLUE}[INFO]${NC}  $(date '+%Y-%m-%d %H:%M:%S') | $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $(date '+%Y-%m-%d %H:%M:%S') | $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date '+%Y-%m-%d %H:%M:%S') | $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') | $*" >&2; }
log_fatal() { echo -e "${RED}${BOLD}[FATAL]${NC} $(date '+%Y-%m-%d %H:%M:%S') | $*" >&2; }

# ---------------------------------------------------------------------------
# Resolve database credentials
# ---------------------------------------------------------------------------
resolve_db_credentials() {
    if [[ -n "${DATABASE_URL:-}" ]]; then
        local url="${DATABASE_URL#mysql+aiomysql://}"
        url="${url#mysql://}"
        DB_USER=$(echo "$url" | sed -n 's/^\([^:]*\):.*/\1/p')
        DB_PASS=$(echo "$url" | sed -n 's/^[^:]*:\([^@]*\)@.*/\1/p')
        DB_HOST=$(echo "$url" | sed -n 's/^[^@]*@\([^:]*\):.*/\1/p')
        DB_PORT=$(echo "$url" | sed -n 's/^[^@]*@[^:]*:\([0-9]*\)\/.*/\1/p')
        DB_NAME=$(echo "$url" | sed -n 's/^[^@]*@[^/]*\/\(.*\)/\1/p')
    elif [[ -n "${MYSQLHOST:-}" ]]; then
        DB_USER="${MYSQLUSER:-root}"
        DB_PASS="${MYSQLPASSWORD:-}"
        DB_HOST="${MYSQLHOST}"
        DB_PORT="${MYSQLPORT:-3306}"
        DB_NAME="${MYSQLDATABASE:-aimp}"
    else
        DB_USER="root"
        DB_PASS="rootpass"
        DB_HOST="localhost"
        DB_PORT="3306"
        DB_NAME="aimp"
    fi

    if [[ -z "${DB_PASS:-}" ]]; then
        log_error "Database password is not set"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Resolve S3/R2 credentials
# ---------------------------------------------------------------------------
resolve_s3_credentials() {
    S3_BUCKET="${S3_BUCKET_NAME:-${R2_BUCKET_NAME:-}}"
    S3_ENDPOINT="${S3_ENDPOINT_URL:-${R2_ENDPOINT_URL:-}}"
    S3_KEY="${S3_ACCESS_KEY_ID:-${R2_ACCESS_KEY_ID:-}}"
    S3_SECRET="${S3_SECRET_ACCESS_KEY:-${R2_SECRET_ACCESS_KEY:-}}"
    S3_REGION="${S3_REGION:-${R2_REGION:-auto}}"
    AWS_ARGS="--endpoint-url ${S3_ENDPOINT} --region ${S3_REGION}"
}

# ---------------------------------------------------------------------------
# List S3 backups
# ---------------------------------------------------------------------------
list_s3_backups() {
    resolve_s3_credentials
    log_info "Listing S3 backups..."
    AWS_ACCESS_KEY_ID="$S3_KEY" \
    AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
    aws s3 ls "s3://${S3_BUCKET}/db-backups/" ${AWS_ARGS} --recursive | \
    grep '\.sql\.gz$' | \
    sort -r | \
    head -20 | \
    nl
}

# ---------------------------------------------------------------------------
# List local backups
# ---------------------------------------------------------------------------
list_local_backups() {
    local backup_dir="${PROJECT_DIR}/backups"
    if [[ ! -d "$backup_dir" ]]; then
        log_warn "No local backup directory found at ${backup_dir}"
        return
    fi
    log_info "Listing local backups..."
    find "$backup_dir" -name '*.sql.gz' -o -name '*.sql' | sort -r | head -20 | nl
}

# ---------------------------------------------------------------------------
# Find latest S3 backup
# ---------------------------------------------------------------------------
find_latest_s3() {
    resolve_s3_credentials
    local latest_key
    latest_key=$(AWS_ACCESS_KEY_ID="$S3_KEY" \
        AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
        aws s3 ls "s3://${S3_BUCKET}/db-backups/" ${AWS_ARGS} --recursive | \
        grep '\.sql\.gz$' | sort -r | head -1 | awk '{print $4}')

    if [[ -z "$latest_key" ]]; then
        log_error "No S3 backups found"
        exit 1
    fi
    echo "s3://${S3_BUCKET}/${latest_key}"
}

# ---------------------------------------------------------------------------
# Find latest local backup
# ---------------------------------------------------------------------------
find_latest_local() {
    local backup_dir="${PROJECT_DIR}/backups"
    local latest_file
    latest_file=$(find "$backup_dir" -name '*.sql.gz' 2>/dev/null | sort -r | head -1)

    if [[ -z "$latest_file" ]]; then
        log_error "No local backups found in ${backup_dir}"
        exit 1
    fi
    echo "$latest_file"
}

# ---------------------------------------------------------------------------
# Download from S3
# ---------------------------------------------------------------------------
download_from_s3() {
    local s3_url="$1"
    local dest="$2"

    log_info "Downloading from S3: ${s3_url}"
    if AWS_ACCESS_KEY_ID="$S3_KEY" \
       AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
       aws s3 cp "$s3_url" "$dest" ${AWS_ARGS}; then
        log_ok "Download completed: $(stat -f%z "$dest" 2>/dev/null || stat -c%s "$dest" 2>/dev/null) bytes"
    else
        log_error "Failed to download from S3"
        exit 2
    fi
}

# ---------------------------------------------------------------------------
# Restore database
# ---------------------------------------------------------------------------
restore_database() {
    local backup_file="$1"
    local decompressed_file="$backup_file"

    resolve_db_credentials
    mkdir -p "$RESTORE_DIR"

    # Decompress if gzipped
    if [[ "$backup_file" == *.gz ]]; then
        decompressed_file="${RESTORE_DIR}/restore_${TIMESTAMP}.sql"
        log_info "Decompressing backup..."
        if gunzip -c "$backup_file" > "$decompressed_file"; then
            log_ok "Decompressed to ${decompressed_file}"
        else
            log_error "Failed to decompress backup"
            exit 3
        fi
    fi

    # Validate SQL file (check header)
    if ! head -5 "$decompressed_file" | grep -qiE '(MySQL dump|Server version|Database)'; then
        log_warn "Backup file does not look like a MySQL dump. First lines:"
        head -5 "$decompressed_file" | while read -r l; do log_warn "  $l"; done
    fi

    # Test database connectivity
    log_info "Testing database connection to ${DB_HOST}:${DB_PORT}..."
    if ! mysql \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --user="${DB_USER}" \
        --password="${DB_PASS}" \
        -e "SELECT 1" >/dev/null 2>&1; then
        log_error "Cannot connect to database. Check credentials and network."
        exit 3
    fi
    log_ok "Database connection successful"

    # Count current tables for comparison
    TABLE_COUNT_BEFORE=$(mysql \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --user="${DB_USER}" \
        --password="${DB_PASS}" \
        -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}'" 2>/dev/null || echo "0")
    log_info "Current tables in ${DB_NAME}: ${TABLE_COUNT_BEFORE}"

    # CONFIRMATION PROMPT
    echo ""
    echo -e "${RED}${BOLD}=======================================================================${NC}"
    echo -e "${RED}${BOLD} WARNING: This will DROP and recreate database: ${DB_NAME}${NC}"
    echo -e "${RED}${BOLD} All existing data in ${DB_NAME} will be PERMANENTLY DELETED.${NC}"
    echo -e "${RED}${BOLD}=======================================================================${NC}"
    echo ""
    echo -n "Type the database name '${DB_NAME}' to confirm: "
    read -r CONFIRM
    if [[ "$CONFIRM" != "$DB_NAME" ]]; then
        log_fatal "Restore cancelled by user"
        exit 1
    fi

    # Create database if not exists (for fresh restore)
    log_info "Creating database ${DB_NAME} if needed..."
    mysql \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --user="${DB_USER}" \
        --password="${DB_PASS}" \
        -e "CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\`;" 2>/dev/null || true

    # Restore
    log_info "Starting restore... This may take several minutes for large databases."
    RESTORE_START=$(date +%s)

    if mysql \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --user="${DB_USER}" \
        --password="${DB_PASS}" \
        --database="${DB_NAME}" \
        < "$decompressed_file" 2>"${RESTORE_DIR}/restore_${TIMESTAMP}.stderr"; then
        RESTORE_END=$(date +%s)
        RESTORE_DURATION=$((RESTORE_END - RESTORE_START))
        log_ok "Restore completed in ${RESTORE_DURATION}s"
    else
        log_error "Restore failed:"
        cat "${RESTORE_DIR}/restore_${TIMESTAMP}.stderr" | tail -20 >&2
        exit 3
    fi

    # Verify restore
    TABLE_COUNT_AFTER=$(mysql \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --user="${DB_USER}" \
        --password="${DB_PASS}" \
        -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}'" 2>/dev/null || echo "0")
    log_info "Tables after restore: ${TABLE_COUNT_AFTER}"

    if [[ "$TABLE_COUNT_AFTER" -lt 1 ]]; then
        log_error "Restore verification failed - no tables found in database"
        exit 3
    fi

    # Show some stats
    log_info "Verifying key tables..."
    mysql \
        --host="${DB_HOST}" \
        --port="${DB_PORT}" \
        --user="${DB_USER}" \
        --password="${DB_PASS}" \
        -e "
        SELECT 'users' as table_name, COUNT(*) as row_count FROM \`${DB_NAME}\`.users
        UNION ALL
        SELECT 'companies', COUNT(*) FROM \`${DB_NAME}\`.companies
        UNION ALL
        SELECT 'branches', COUNT(*) FROM \`${DB_NAME}\`.branches
        UNION ALL
        SELECT 'events', COUNT(*) FROM \`${DB_NAME}\`.events
        UNION ALL
        SELECT 'event_logs', COUNT(*) FROM \`${DB_NAME}\`.event_logs
        " 2>/dev/null || log_warn "Could not verify all tables"

    # Cleanup
    rm -f "$decompressed_file" "${RESTORE_DIR}/restore_${TIMESTAMP}.stderr"
    rmdir "$RESTORE_DIR" 2>/dev/null || true

    echo ""
    log_ok "=== RESTORE COMPLETED SUCCESSFULLY ==="
    log_info "  Duration:     ${RESTORE_DURATION}s"
    log_info "  Tables:       ${TABLE_COUNT_BEFORE} -> ${TABLE_COUNT_AFTER}"
    log_info "  Backup:       ${backup_file}"
    log_info "  Timestamp:    ${TIMESTAMP}"
    echo ""
    log_warn "You may need to restart the application for all caches to clear"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    mkdir -p "$RESTORE_DIR"

    if [[ $# -lt 1 ]]; then
        echo "Usage:"
        echo "  $0 s3://bucket/path/to/backup.sql.gz     # Restore from S3 URL"
        echo "  $0 local /path/to/backup.sql.gz           # Restore from local file"
        echo "  $0 latest                                 # Restore latest S3 backup"
        echo "  $0 latest-local                           # Restore latest local backup"
        echo "  $0 --list-s3                              # List S3 backups"
        echo "  $0 --list-local                           # List local backups"
        exit 1
    fi

    case "$1" in
        --list-s3)
            list_s3_backups
            ;;
        --list-local)
            list_local_backups
            ;;
        latest)
            resolve_s3_credentials
            LATEST=$(find_latest_s3)
            LOCAL_FILE="${RESTORE_DIR}/$(basename "$LATEST")"
            download_from_s3 "$LATEST" "$LOCAL_FILE"
            restore_database "$LOCAL_FILE"
            rm -f "$LOCAL_FILE"
            ;;
        latest-local)
            LATEST=$(find_latest_local)
            restore_database "$LATEST"
            ;;
        s3://*)
            resolve_s3_credentials
            LOCAL_FILE="${RESTORE_DIR}/$(basename "$1")"
            download_from_s3 "$1" "$LOCAL_FILE"
            restore_database "$LOCAL_FILE"
            rm -f "$LOCAL_FILE"
            ;;
        local)
            if [[ ! -f "$2" ]]; then
                log_error "Local file not found: $2"
                exit 1
            fi
            restore_database "$2"
            ;;
        *)
            if [[ -f "$1" ]]; then
                restore_database "$1"
            else
                log_error "Unknown argument or file not found: $1"
                exit 1
            fi
            ;;
    esac

    rmdir "$RESTORE_DIR" 2>/dev/null || true
}

main "$@"
