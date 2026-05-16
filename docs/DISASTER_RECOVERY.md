# Disaster Recovery Plan - AI Marketing Platform v2.0

## 1. Overview

This document defines the disaster recovery (DR) procedures for the AI Marketing Platform (AIMP). It covers data loss scenarios, service failures, infrastructure outages, and the step-by-step recovery procedures for each.

### Recovery Objectives

| Metric | Target | Actual |
|--------|--------|--------|
| **RPO** (Recovery Point Objective) | < 1 hour | 15 min (automated backups) |
| **RTO** (Recovery Time Objective) | < 4 hours | 1-2 hours |
| **Backup Frequency** | Every 6 hours | Every 6 hours |
| **Backup Retention** | 30 days | 30 days |

### Contact Information

| Role | Contact | Escalation |
|------|---------|------------|
| DevOps Lead | devops@company.com | +1-555-DEV-OPS |
| Backend Lead | backend@company.com | +1-555-BACK-END |
| On-call Pager | pagerduty.com/aimp | Automatic rotation |

---

## 2. Risk Assessment

### 2.1 Risk Matrix

| Risk | Probability | Impact | Priority |
|------|------------|--------|----------|
| Database corruption/failure | Low | Critical | P1 |
| Complete data center outage | Low | Critical | P1 |
| Accidental data deletion | Medium | High | P1 |
| Railway platform outage | Low | High | P2 |
| Redis failure (cache loss) | Medium | Medium | P2 |
| CDN/storage failure | Low | Medium | P2 |
| RabbitMQ failure | Medium | Medium | P3 |
| Slow database queries | High | Low | P3 |

### 2.2 Failure Scenarios

```
Scenario Classification:
- Critical (P1): Complete service unavailability or data loss
- High (P2): Degraded service or partial data loss
- Medium (P3): Reduced performance or non-critical feature down
```

---

## 3. Backup Strategy

### 3.1 Automated Backups

| Type | Frequency | Retention | Storage |
|------|-----------|-----------|---------|
| Full DB dump | Every 6 hours | 30 days | S3/R2 |
| Incremental binlog | Continuous | 7 days | S3/R2 |
| Redis AOF | Continuous | N/A | Local + S3 |
| Qdrant snapshots | Daily | 7 days | S3/R2 |
| Grafana dashboards | On change | 30 days | Git |

### 3.2 Running a Manual Backup

```bash
# Full backup with upload to S3/R2
./scripts/backup-db.sh

# Dry run (no upload)
./scripts/backup-db.sh --dry-run

# Incremental backup (binlog-based)
./scripts/backup-db.sh --incremental
```

### 3.3 Backup Verification

Backups are automatically verified by:
1. Checking MySQL dump header validity
2. Testing gzip integrity
3. Recording row counts of key tables in metadata
4. Weekly restore tests on staging environment

---

## 4. Recovery Procedures

### 4.1 Scenario: Complete Database Failure (P1)

**Symptoms:** MySQL unreachable, 5xx errors, readiness probe failing

**Impact:** Complete service unavailability

**Recovery Steps:**

```bash
# Step 1: Confirm the failure
curl http://API_URL/api/v2/health/db
# Expected: {"status": "unhealthy", ...}

# Step 2: Identify the most recent backup
./scripts/restore-db.sh --list-s3
# Or for local:
./scripts/restore-db.sh --list-local

# Step 3: Restore from the latest backup
./scripts/restore-db.sh latest
# Or specify a backup:
# ./scripts/restore-db.sh s3://bucket/db-backups/2025/01/15/backup.sql.gz

# Step 4: Verify the restore
./scripts/smoke-test.sh --health-only

# Step 5: Restart application to clear caches
docker compose restart backend

# Step 6: Verify full system health
./scripts/smoke-test.sh
```

**Expected Recovery Time:** 30-60 minutes

---

### 4.2 Scenario: Accidental Data Deletion (P1)

**Symptoms:** Data missing from tables, user reports, audit log anomalies

**Recovery Steps:**

```bash
# Step 1: Stop writes to prevent further damage
docker compose stop celery_worker celery_beat

# Step 2: Find a backup from BEFORE the deletion
# List backups with timestamps
./scripts/restore-db.sh --list-s3

# Step 3: Restore to a temporary database
# (Avoid overwriting current DB in case you need to compare)
mysql -h localhost -u root -p -e "CREATE DATABASE aimp_recovery;"

# Step 4: Manually extract and merge the deleted data
# Use mysqldump to export specific tables from recovery DB
# Then import into the main database

# Step 5: Verify data integrity
./scripts/smoke-test.sh --crud-only

# Step 6: Resume background jobs
docker compose start celery_worker celery_beat
```

---

### 4.3 Scenario: Railway Platform Outage (P2)

**Symptoms:** Railway dashboard shows platform issues, all services unreachable

**Recovery Steps:**

```bash
# Step 1: Confirm Railway status
# Check https://status.railway.app/

# Step 2: If outage is extended, deploy to alternative region
# In Railway dashboard:
#   - Settings > Deploy Region > Change to alternative region

# Step 3: Verify DNS propagation
dig +short YOUR_APP.up.railway.app

# Step 4: Verify connectivity
./scripts/smoke-test.sh --railway --url https://NEW_URL.up.railway.app
```

---

### 4.4 Scenario: Redis Failure (P2)

**Symptoms:** Cache misses, sessions lost, rate limiting not working

**Recovery Steps:**

```bash
# Step 1: Check Redis health
curl http://API_URL/api/v2/health/redis

# Step 2: Restart Redis container
docker compose restart redis

# Step 3: Verify Redis AOF recovery
docker compose logs redis | tail -20

# Step 4: If AOF is corrupt, force recovery
docker compose exec redis redis-cli BGREWRITEAOF

# Step 5: Application will repopulate caches automatically
# Verify:
./scripts/smoke-test.sh --health-only
```

---

### 4.5 Scenario: Storage/CDN Failure (P2)

**Symptoms:** Media assets not loading, upload failures

**Recovery Steps:**

```bash
# Step 1: Check storage endpoint
aws s3 ls s3://$S3_BUCKET_NAME/ --endpoint-url $S3_ENDPOINT_URL

# Step 2: If R2 is down, switch to S3 or local temporarily
# Edit backend/.env:
#   STORAGE_PROVIDER=s3
#   S3_ENDPOINT_URL=https://s3.amazonaws.com

# Step 3: Restart backend
docker compose restart backend
```

---

## 5. Monitoring & Alerting

### 5.1 Prometheus Alerts

All critical alerts are defined in `monitoring/rules/alerting_rules.yml`:

| Alert | Severity | Trigger | Action |
|-------|----------|---------|--------|
| `AIMP_API_Down` | critical | API unreachable for 1m | Page on-call |
| `AIMP_HighErrorRate` | critical | >10% 5xx errors for 2m | Page on-call |
| `AIMP_DatabaseDown` | critical | MySQL unreachable for 1m | Page on-call |
| `AIMP_RedisDown` | critical | Redis unreachable for 1m | Page on-call |
| `AIMP_ElevatedErrorRate` | warning | >5% 5xx errors for 5m | Slack alert |
| `AIMP_DBSlowQueries` | critical | DB p95 > 1s for 5m | Page on-call |
| `AIMP_DiskFull` | critical | <5% disk space | Page on-call |

### 5.2 Grafana Dashboards

| Dashboard | URL | Purpose |
|-----------|-----|---------|
| API Performance | Grafana > AIMP - API Performance | Request rates, latency, connections |
| Error Rate | Grafana > AIMP - Error Rate | 5xx/4xx rates, top errors |
| AI Usage | Grafana > AIMP - AI Usage | Token usage, cost, latency |
| Infrastructure | Grafana > AIMP - Infrastructure | CPU, memory, disk, network |

---

## 6. Runbooks

### 6.1 Database Recovery Runbook

1. **Assess** - Check `/api/v2/health/db` for specific error
2. **Isolate** - Stop writes: `docker compose stop celery_worker`
3. **Backup** - If DB is partially accessible, take emergency backup: `./scripts/backup-db.sh`
4. **Restore** - Run `./scripts/restore-db.sh latest`
5. **Verify** - Run `./scripts/smoke-test.sh`
6. **Communicate** - Notify team in #incidents Slack channel

### 6.2 High Error Rate Runbook

1. **Check** - Review Grafana Error Rate dashboard
2. **Identify** - Check logs for the failing endpoint
3. **Rollback** - If caused by deployment, rollback via Railway dashboard
4. **Scale** - If caused by traffic, scale up workers in railway.toml
5. **Verify** - Run `./scripts/smoke-test.sh`

### 6.3 AI API Failure Runbook

1. **Check** - Review Grafana AI Usage dashboard
2. **Verify** - Check external API status (OpenAI, Meta, Google)
3. **Fallback** - Enable supervised mode if AI is down
4. **Queue** - Background jobs will retry with exponential backoff

---

## 7. Testing & Drills

### 7.1 Recovery Testing Schedule

| Test | Frequency | Owner |
|------|-----------|-------|
| Full backup + restore test | Weekly | DevOps |
| Failover test (Railway) | Monthly | DevOps |
| Smoke test suite | Every deployment | CI/CD |
| DR plan review | Quarterly | Team |

### 7.2 Recovery Test Procedure

```bash
# 1. Run full smoke test
./scripts/smoke-test.sh --verbose

# 2. Test backup
./scripts/backup-db.sh --dry-run

# 3. Test restore to staging (manual quarterly)
./scripts/restore-db.sh latest

# 4. Verify all dashboards load
curl -s http://localhost:9090/api/v1/status/targets | jq '.data.activeTargets'
```

---

## 8. Infrastructure Diagram

```
Internet -> Railway LB -> Backend API -> MySQL
                                      -> Redis
                                      -> RabbitMQ
                                      -> Qdrant
                                      
Monitoring: Prometheus -> Grafana -> Alertmanager -> Slack/PagerDuty
           Loki        -> Grafana
```

---

## 9. Document History

| Date | Version | Author | Changes |
|------|---------|--------|---------|
| 2025-01 | 1.0 | DevOps Team | Initial DR plan |
| 2025-01 | 2.0 | DevOps Team | Added monitoring stack, automated scripts |

---

*This document should be reviewed quarterly and updated after every incident.*
