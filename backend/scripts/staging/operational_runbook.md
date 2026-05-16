# AIMP v2.0 Staging Operational Runbook

## Quick Reference

| Service | URL | Health Check |
|---------|-----|-------------|
| Backend API | http://localhost:8001/api/v2/health | `curl http://localhost:8001/api/v2/health` |
| DB | localhost:3307 | `mysqladmin -P3307 ping` |
| Redis | localhost:6380 | `redis-cli -p 6380 ping` |
| MinIO | localhost:9001 | `curl http://localhost:9001/minio/health/live` |
| Grafana | localhost:3001 | `curl http://localhost:3001/api/health` |
| Prometheus | localhost:9091 | `curl http://localhost:9091/-/healthy` |

## Daily Operations

### 1. Check System Health
```bash
cd backend && python scripts/staging_health_check.py --host http://localhost:8001
```

### 2. Check Migration Status
```bash
cd backend && alembic current
cd backend && python scripts/quality/alembic_drift_check.py
```

### 3. Check Queue Status
```bash
docker logs aimp_staging_celery --tail 100
docker exec aimp_staging_redis redis-cli -p 6379 LLEN celery
```

### 4. Run Smoke Tests
```bash
cd backend && python scripts/staging_smoke_test.py --host http://localhost:8001
cd backend && pytest app/tests/ -v
```

## Common Issues

### MySQL Connection Failed
```bash
docker logs aimp_staging_mysql --tail 50
docker restart aimp_staging_mysql
```

### Celery Worker Down
```bash
docker restart aimp_staging_celery
docker logs aimp_staging_celery --tail 50
```

### Migration Stuck
```bash
cd backend && alembic stamp head
cd backend && alembic upgrade head --sql > migration.sql
```

## Deployment

### Staging Deploy
```bash
docker compose -f docker-compose.staging.yml down
docker compose -f docker-compose.staging.yml up -d --build
```

### View All Logs
```bash
docker compose -f docker-compose.staging.yml logs -f
```

### Emergency Rollback
```bash
cd backend && alembic downgrade -1
docker compose -f docker-compose.staging.yml restart backend
```

## Contacts
- Platform Engineer: On-call rotation
- Backend Team: Slack #aimp-backend
- Customer Success: Slack #aimp-customer
