# Pilot Rollback Plan

## Rollback Levels

### Level 1: Feature Flag Rollback (30 seconds)
- Disable specific feature via `/api/v2/rollout/feature/{name}`
- No deployment required
- Customer impact: feature disappears from UI
- Use for: feature-specific bugs, AI safety issues

### Level 2: Tenant-Level Rollback (2 minutes)
- Disable all features for specific tenant
- Restore tenant to previous feature set
- Use for: tenant-specific issues, data integrity problems

### Level 3: API Version Rollback (5 minutes)
- Switch API version via version header
- Previous API version remains operational
- Use for: breaking API changes

### Level 4: Deployment Rollback (15 minutes)
- Roll back to previous Docker image tag
- Restart backend containers
- Use for: systemic issues, multiple feature failures

### Level 5: Database Rollback (60+ minutes)
- Restore from backup
- Requires DBA involvement
- Use for: data corruption, migration failures
- **This is a last resort for pilot**

## Rollback Decision Tree

```
Issue detected
    |
    +-- Is it a single feature? ---------------> Level 1 (Feature flag)
    |   Can be isolated?
    |
    +-- Is it a single tenant? ----------------> Level 2 (Tenant isolation)
    |   Others unaffected?
    |
    +-- Is it API-breaking? -------------------> Level 3 (API rollback)
    |   Previous version works?
    |
    +-- Are multiple features broken? ---------> Level 4 (Deploy rollback)
    |   Systemic issue?
    |
    +-- Is there data corruption? -------------> Level 5 (DB restore)
        CRITICAL - Last resort
```

## Pilot Rollback Procedures

### Feature Flag Rollback
```bash
# 1. Check current feature flags
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/v2/rollout/features

# 2. Disable feature for tenant
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "pilot_001", "feature": "ai_chat", "enabled": false}' \
  http://localhost:8001/api/v2/rollout/feature/toggle

# 3. Verify
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/v2/rollout/features | grep ai_chat
```

### Deployment Rollback
```bash
# 1. List available images
docker images | grep aimp-backend

# 2. Tag previous image as current
docker tag aimp-backend:previous aimp-backend:current

# 3. Rolling restart
docker compose -f docker-compose.staging.yml up -d --no-deps --build backend

# 4. Verify health
curl http://localhost:8001/api/v2/health
curl http://localhost:8001/api/v2/health/db
curl http://localhost:8001/api/v2/health/redis

# 5. Verify all routers responding
curl http://localhost:8001/api/v2/health/queue
```

### Database Rollback (Last Resort)
```bash
# 1. Stop all writes
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/v2/admin/maintenance-mode/enable

# 2. Backup current state (even if corrupted)
mysqldump -h localhost -P 3307 -u aimp_staging -p aimp_staging > \
  /backup/pre_rollback_$(date +%Y%m%d_%H%M%S).sql

# 3. Restore from backup
mysql -h localhost -P 3307 -u aimp_staging -p aimp_staging < \
  /backup/last_known_good.sql

# 4. Run migrations to catch up
alembic upgrade head

# 5. Disable maintenance mode
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8001/api/v2/admin/maintenance-mode/disable

# 6. Verify
curl http://localhost:8001/api/v2/health/db
```

## Rollback Testing

| Test | Frequency | Owner |
|------|-----------|-------|
| Feature flag toggle | Weekly | L2 Support |
| Deployment rollback | Monthly | DevOps |
| DB restore from backup | Monthly | DBA |
| Full rollback simulation | Before pilot | Engineering |

## Pilot-Specific Rollback Triggers

| Condition | Rollback Level | Max Time |
|-----------|---------------|----------|
| AI auto-send enabled accidentally | L1 | 30 sec |
| Customer data visible to other tenant | L2 | 2 min |
| API returning 500 > 10% requests | L4 | 15 min |
| Data corruption detected | L5 | 60 min |
| Security breach suspected | L2 + L4 | 5 min |
| > 3 P1 incidents in 24h | L4 | 15 min |

## Communication During Rollback

1. **Start**: Notify pilot customers within 5 minutes
2. **During**: Update every 15 minutes until resolved
3. **End**: Postmortem scheduled within 48 hours
4. **All comms**: Slack #pilot-ops + email
