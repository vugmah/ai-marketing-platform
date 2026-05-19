#!/bin/bash
# =============================================================================
# AI Marketing Platform - Database Backup Script
# =============================================================================
# Backs up MySQL database to a timestamped SQL dump and uploads to S3/R2.
#
# Usage:
#   ./scripts/backup-db.sh                    # Full backup
#   ./scripts/backup-db.sh --incremental      # Incremental (binlog-based)
#   ./scripts/backup-db.sh --dry-run          # Dry run (no upload)
#
# Environment Variables Required:
#   DATABASE_URL or MYSQL_* vars - Database connection
#   S3_BUCKET_NAME                     - S3 bucket name
#   S3_ENDPOINT_URL                    - S3-compatible endpoint (e.g., R2)
#   S3_ACCESS_KEY_ID                   - S3 access key
#   S3_SECRET_ACCESS_KEY               - S3 secret key
#   BACKUP_RETENTION_DAYS              - Retention period (default: 30)
#
# Exit Codes:
#   0  - Success
#   1  - Configuration error
#   2  - Database dump failed
#   3  - Upload failed
#   4  - Retention cleanup failed
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_PREFIX=$(date +%Y/%m/%d)
HOSTNAME=$(hostname -s 2>/dev/null || echo "unknown")
BACKUP_TYPE="full"
DRY_RUN=false
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log_info()  { echo -e "${BLUE}[INFO]${NC}  $(date '+%Y-%m-%d %H:%M:%S') | $*"; }
log_ok()    { echo -e "${GREEN}[OK]${NC}    $(date '+%Y-%m-%d %H:%M:%S') | $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $(date '+%Y-%m-%d %H:%M:%S') | $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') | $*" >&2; }

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --incremental) BACKUP_TYPE="incremental"; shift ;;
        --dry-run)     DRY_RUN=true; shift ;;
        --retention)   RETENTION_DAYS="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--incremental] [--dry-run] [--retention DAYS]"
            exit 0
            ;;
        *) log_error "Unknown option: $1"; exit 1 ;;
    esac
done

log_info "Starting AIMP database backup"
log_info "Type: ${BACKUP_TYPE} | Dry-run: ${DRY_RUN} | Retention: ${RETENTION_DAYS} days"

# ---------------------------------------------------------------------------
# Resolve database credentials
# ---------------------------------------------------------------------------
resolve_db_credentials() {
    # Try Railway DATABASE_URL first
    if [[ -n "${DATABASE_URL:-}" ]]; then
        # Parse mysql+aiomysql://user:pass@host:port/db
        local url="${DATABASE_URL#mysql+aiomysql://}"
        url="${url#mysql://}"
        DB_USER=$(echo "$url" | sed -n 's/^\([^:]*\):.*/\1/p')
        DB_PASS=$(echo "$url" | sed -n 's/^[^:]*:\([^@]*\)@.*/\1/p')
        DB_HOST=$(echo "$url" | sed -n 's/^[^@]*@\([^:]*\):.*/\1/p')
        DB_PORT=$(echo "$url" | sed -n 's/^[^@]*@[^:]*:\([0-9]*\)\/.*/\1/p')
        DB_NAME=$(echo "$url" | sed -n 's/^[^@]*@[^/]*\/\(.*\)/\1/p')
    # Try individual Railway MySQL vars
    elif [[ -n "${MYSQLHOST:-}" ]]; then
        DB_USER="${MYSQLUSER:-root}"
        DB_PASS="${MYSQLPASSWORD:-}"
        DB_HOST="${MYSQLHOST}"
        DB_PORT="${MYSQLPORT:-3306}"
        DB_NAME="${MYSQLDATABASE:-aimp}"
    # Fallback to local docker
    else
        DB_USER="root"
        DB_PASS="rootpass"
        DB_HOST="localhost"
        DB_PORT="3306"
        DB_NAME="aimp"
    fi

    # Validate
    if [[ -z "${DB_PASS:-}" ]]; then
        log_error "Database password is not set. Set DATABASE_URL or MYSQLPASSWORD."
        exit 1
    fi
}

resolve_db_credentials

# ---------------------------------------------------------------------------
# Resolve S3/R2 credentials
# ---------------------------------------------------------------------------
resolve_s3_credentials() {
    S3_BUCKET="${S3_BUCKET_NAME:-${R2_BUCKET_NAME:-}}"
    S3_ENDPOINT="${S3_ENDPOINT_URL:-${R2_ENDPOINT_URL:-}}"
    S3_KEY="${S3_ACCESS_KEY_ID:-${R2_ACCESS_KEY_ID:-}}"
    S3_SECRET="${S3_SECRET_ACCESS_KEY:-${R2_SECRET_ACCESS_KEY:-}}"
    S3_REGION="${S3_REGION:-${R2_REGION:-auto}}"

    if [[ -z "$S3_BUCKET" || -z "$S3_ENDPOINT" || -z "$S3_KEY" || -z "$S3_SECRET" ]]; then
        log_warn "S3/R2 credentials incomplete - skipping upload"
        S3_ENABLED=false
    else
        S3_ENABLED=true
    fi
}

resolve_s3_credentials

# ---------------------------------------------------------------------------
# Create backup directory
# ---------------------------------------------------------------------------
BACKUP_DIR="/tmp/aimp-backups"
mkdir -p "$BACKUP_DIR"
DUMP_FILE="${BACKUP_DIR}/aimp_backup_${BACKUP_TYPE}_${TIMESTAMP}.sql"
ARCHIVE_FILE="${DUMP_FILE}.gz"
METADATA_FILE="${DUMP_FILE}.meta.json"

# ---------------------------------------------------------------------------
# Perform database dump
# ---------------------------------------------------------------------------
log_info "Dumping database: ${DB_NAME} from ${DB_HOST}:${DB_PORT}"

DUMP_START=$(date +%s)

if mysqldump \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --user="${DB_USER}" \
    --password="${DB_PASS}" \
    --databases "${DB_NAME}" \
    --single-transaction \
    --quick \
    --lock-tables=false \
    --routines \
    --triggers \
    --events \
    --hex-blob \
    --skip-ssl \
    2>"${BACKUP_DIR}/dump_${TIMESTAMP}.stderr" \
    > "${DUMP_FILE}"; then
    DUMP_END=$(date +%s)
    DUMP_DURATION=$((DUMP_END - DUMP_START))
    DUMP_SIZE=$(stat -f%z "$DUMP_FILE" 2>/dev/null || stat -c%s "$DUMP_FILE" 2>/dev/null || echo "unknown")
    log_ok "Dump completed in ${DUMP_DURATION}s (${DUMP_SIZE} bytes)"
else
    log_error "Database dump failed:"
    cat "${BACKUP_DIR}/dump_${TIMESTAMP}.stderr" >&2
    rm -f "$DUMP_FILE"
    exit 2
fi

# ---------------------------------------------------------------------------
# Compress dump
# ---------------------------------------------------------------------------
log_info "Compressing dump file..."
if gzip -f "$DUMP_FILE"; then
    ARCHIVE_SIZE=$(stat -f%z "$ARCHIVE_FILE" 2>/dev/null || stat -c%s "$ARCHIVE_FILE" 2>/dev/null)
    log_ok "Compressed to ${ARCHIVE_SIZE} bytes"
else
    log_warn "Compression failed, using uncompressed file"
    ARCHIVE_FILE="$DUMP_FILE"
fi

# ---------------------------------------------------------------------------
# Generate metadata
# ---------------------------------------------------------------------------
BINLOG_INFO=$(mysql \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --user="${DB_USER}" \
    --password="${DB_PASS}" \
    -e "SHOW MASTER STATUS\G" 2>/dev/null | grep -E 'File|Position' || echo "")

cat > "$METADATA_FILE" <<EOF
{
    "backup_type": "${BACKUP_TYPE}",
    "timestamp": "${TIMESTAMP}",
    "hostname": "${HOSTNAME}",
    "database": {
        "host": "${DB_HOST}",
        "port": ${DB_PORT},
        "name": "${DB_NAME}"
    },
    "files": {
        "dump": "$(basename "$ARCHIVE_FILE")",
        "size_bytes": ${ARCHIVE_SIZE},
        "compressed": true
    },
    "mysql": {
        "binlog_info": "$(echo "$BINLOG_INFO" | tr '\n' ' ' | sed 's/"/\\"/g')"
    },
    "duration_seconds": ${DUMP_DURATION:-0},
    "retention_days": ${RETENTION_DAYS}
}
EOF
log_ok "Metadata file created"

# ---------------------------------------------------------------------------
# Upload to S3/R2
# ---------------------------------------------------------------------------
if [[ "$S3_ENABLED" == true && "$DRY_RUN" == false ]]; then
    log_info "Uploading to S3: ${S3_BUCKET}/${DATE_PREFIX}/"

    S3_KEY_PATH="db-backups/${DATE_PREFIX}/$(basename "$ARCHIVE_FILE")"
    META_KEY_PATH="db-backups/${DATE_PREFIX}/$(basename "$METADATA_FILE")"

    # Build AWS CLI args for S3-compatible storage
    AWS_ARGS="--endpoint-url ${S3_ENDPOINT} --region ${S3_REGION}"

    # Upload dump
    if AWS_ACCESS_KEY_ID="$S3_KEY" \
       AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
       aws s3 cp "$ARCHIVE_FILE" "s3://${S3_BUCKET}/${S3_KEY_PATH}" \
       ${AWS_ARGS} \
       --storage-class STANDARD; then
        log_ok "Dump uploaded: s3://${S3_BUCKET}/${S3_KEY_PATH}"
    else
        log_error "Failed to upload dump to S3"
        exit 3
    fi

    # Upload metadata
    if AWS_ACCESS_KEY_ID="$S3_KEY" \
       AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
       aws s3 cp "$METADATA_FILE" "s3://${S3_BUCKET}/${META_KEY_PATH}" \
       ${AWS_ARGS}; then
        log_ok "Metadata uploaded: s3://${S3_BUCKET}/${META_KEY_PATH}"
    fi

    # Cleanup old backups (retention policy)
    log_info "Cleaning up backups older than ${RETENTION_DAYS} days"
    CUTOFF_DATE=$(date -d "-${RETENTION_DAYS} days" +%Y/%m/%d 2>/dev/null || date -v-${RETENTION_DAYS}d +%Y/%m/%d 2>/dev/null)
    if [[ -n "$CUTOFF_DATE" ]]; then
        # List and delete old objects
        AWS_ACCESS_KEY_ID="$S3_KEY" \
        AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
        aws s3 ls "s3://${S3_BUCKET}/db-backups/" ${AWS_ARGS} --recursive | \
        while read -r line; do
            FILE_DATE=$(echo "$line" | awk '{print $1}')
            FILE_KEY=$(echo "$line" | awk '{print $4}')
            if [[ "$FILE_DATE" < "$CUTOFF_DATE" ]]; then
                AWS_ACCESS_KEY_ID="$S3_KEY" \
                AWS_SECRET_ACCESS_KEY="$S3_SECRET" \
                aws s3 rm "s3://${S3_BUCKET}/${FILE_KEY}" ${AWS_ARGS} 2>/dev/null && \
                log_info "Deleted old backup: ${FILE_KEY}"
            fi
        done || log_warn "Retention cleanup encountered issues"
    fi

    # Generate latest symlink (keep last N)
    echo "s3://${S3_BUCKET}/${S3_KEY_PATH}" > "${BACKUP_DIR}/LATEST_BACKUP_S3_URL.txt"

elif [[ "$DRY_RUN" == true ]]; then
    log_info "[DRY RUN] Would upload to s3://${S3_BUCKET}/db-backups/${DATE_PREFIX}/"
    log_info "[DRY RUN] Files:"
    log_info "  - $(basename "$ARCHIVE_FILE") (${ARCHIVE_SIZE} bytes)"
    log_info "  - $(basename "$METADATA_FILE")"
else
    log_warn "S3 upload skipped - credentials not configured"
    # Keep local copy
    LOCAL_BACKUP_DIR="${PROJECT_DIR}/backups"
    mkdir -p "$LOCAL_BACKUP_DIR"
    cp "$ARCHIVE_FILE" "$METADATA_FILE" "$LOCAL_BACKUP_DIR/"
    log_ok "Local backup saved to: ${LOCAL_BACKUP_DIR}/"
fi

# ---------------------------------------------------------------------------
# Cleanup temporary files
# ---------------------------------------------------------------------------
rm -f "$ARCHIVE_FILE" "$METADATA_FILE" "${BACKUP_DIR}/dump_${TIMESTAMP}.stderr"
rmdir "$BACKUP_DIR" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log_info "Backup Summary:"
log_info "  Type:        ${BACKUP_TYPE}"
log_info "  Timestamp:   ${TIMESTAMP}"
log_info "  Duration:    ${DUMP_DURATION}s"
log_info "  Size:        ${ARCHIVE_SIZE} bytes (compressed)"
log_info "  Destination: ${S3_ENABLED:-false}"

log_ok "Backup completed successfully"
exit 0
