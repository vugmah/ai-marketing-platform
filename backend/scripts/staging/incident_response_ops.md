# Incident Response Operations

## Severity Matrix

| Severity | Criteria | Response Time | Resolution Target | Communication |
|----------|----------|---------------|-------------------|---------------|
| P1 - Critical | Complete outage, data loss, security breach, AI safety violation | 15 min | 2 hours | Customer within 30 min |
| P2 - High | Major feature broken, significant performance degradation, ERP sync failure | 1 hour | 4 hours | Customer within 2 hours |
| P3 - Medium | Feature partially broken, workaround exists, single tenant issue | 4 hours | 24 hours | Customer within 8 hours |
| P4 - Low | Cosmetic issue, documentation gap, enhancement request | 24 hours | 72 hours | Next business day |

## Escalation Chain

```
L1 Support (Business Hours)
    | 15 min no response
    v
L2 Technical (Business Hours + On-call)
    | 30 min unresolved OR P1/P2
    v
L3 Engineering (24/7 On-call)
    | P1 OR > 1 hour unresolved
    v
Engineering Lead + Product Manager
    | Data loss OR security OR > 2 hours
    v
Executive (CTO/VP)
```

## Rollback Procedures

### Procedure A: Feature Flag Rollback (30 seconds)
```bash
# Check current state
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  $API/api/v2/rollout/feature/{feature_name}/status

# Disable for tenant
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "pilot_XXX", "enabled": false}' \
  $API/api/v2/rollout/feature/{feature_name}/toggle

# Verify
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  $API/api/v2/rollout/feature/{feature_name}/status
```

### Procedure B: Deployment Rollback (15 minutes)
```bash
# 1. Identify previous image
docker images --format "{{.Repository}}:{{.Tag}}" | grep aimp-backend

# 2. Tag rollback
docker tag aimp-backend:{previous_tag} aimp-backend:rollback

# 3. Rolling restart
docker compose -f docker-compose.staging.yml stop backend
docker compose -f docker-compose.staging.yml rm -f backend
docker compose -f docker-compose.staging.yml up -d backend

# 4. Verify all health checks
curl $API/api/v2/health      # Should return 200
curl $API/api/v2/health/db  # Should return 200
curl $API/api/v2/health/redis # Should return 200

# 5. Verify key endpoints
curl $API/api/v2/health/queue
curl $API/docs
```

### Procedure C: AI Outage Response (5 minutes)
```bash
# 1. Check AI health
curl $API/api/v2/ai-cost/models

# 2. If AI provider down, switch to fallback
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fallback_model": "gpt-4o-mini", "max_tokens": 1000}' \
  $API/api/v2/ai-cost/budget

# 3. Disable AI features if needed
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "pilot_XXX", "enabled": false}' \
  $API/api/v2/rollout/feature/ai_chat/toggle

# 4. Enable maintenance mode for AI endpoints
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  $API/api/v2/admin/maintenance/ai/enable
```

### Procedure D: Redis Outage Response (10 minutes)
```bash
# 1. Check Redis
docker logs aimp_staging_redis --tail 50
redis-cli -p 6380 ping

# 2. Restart Redis
docker compose -f docker-compose.staging.yml restart redis

# 3. Wait for health check
curl $API/api/v2/health/redis

# 4. If persistent issues, check persistence
docker exec aimp_staging_redis redis-cli info persistence

# 5. Verify Celery recovers
curl $API/api/v2/health/queue
docker logs aimp_staging_celery --tail 20
```

### Procedure E: Celery Failure Response (10 minutes)
```bash
# 1. Check worker status
docker logs aimp_staging_celery --tail 50
celery -A app.celery_app inspect active
celery -A app.celery_app inspect reserved

# 2. Check queue depth
redis-cli -p 6380 LLEN celery

# 3. Restart workers
docker compose -f docker-compose.staging.yml restart celery_worker

# 4. Verify
celery -A app.celery_app inspect ping
curl $API/api/v2/health/queue
```

### Procedure F: DB Failover Response (30 minutes)
```bash
# 1. Check MySQL
docker logs aimp_staging_mysql --tail 50
mysql -h 127.0.0.1 -P 3307 -u aimp_staging -p -e "SHOW PROCESSLIST;"

# 2. Check connection count
mysql -h 127.0.0.1 -P 3307 -u aimp_staging -p -e "SHOW STATUS LIKE 'Threads_connected';"

# 3. If unresponsive, restart
docker compose -f docker-compose.staging.yml restart mysql

# 4. After restart, verify migrations
alembic current
alembic history --verbose

# 5. Run health check
curl $API/api/v2/health/db
```

### Procedure G: Webhook Outage Response (15 minutes)
```bash
# 1. Check webhook delivery status
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  $API/api/v2/observability/webhook-health

# 2. Check failure logs
grep "webhook" /var/log/aimp/backend.log | tail -50

# 3. Retry failed webhooks
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  $API/api/v2/observability/webhook-retry

# 4. If external service down, enable queuing
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"queue_failed": true, "retry_interval": 300}' \
  $API/api/v2/observability/webhook-config
```

## Postmortem Template

### Incident Postmortem

```markdown
# Postmortem: INC-{YYYY}-{NNN}

## Summary
- **Incident ID**: INC-2026-XXX
- **Date**: YYYY-MM-DD
- **Severity**: P1/P2/P3/P4
- **Duration**: XX minutes
- **Affected tenants**: pilot_XXX

## Timeline
- HH:MM - Issue detected (by monitoring/customer/support)
- HH:MM - Escalated to L2
- HH:MM - Root cause identified
- HH:MM - Fix applied
- HH:MM - Service restored
- HH:MM - Postmortem started

## Root Cause
[What caused the incident?]

## Impact
- Affected users: X
- Data lost: Yes/No (if yes, how much)
- Revenue impact: $X
- Customer satisfaction impact: X/10

## Resolution
[How was it fixed?]

## What Went Well
1.
2.

## What Went Wrong
1.
2.

## Action Items
| # | Action | Owner | Due Date | Priority |
|---|--------|-------|----------|----------|
| 1 | | | | |
| 2 | | | | |

## Prevention
[How do we prevent this from happening again?]
```

## Repeat Incident Tracking

| Incident Type | Count | Last Occurrence | Status |
|---------------|-------|-----------------|--------|
| AI provider timeout | | | |
| Redis memory full | | | |
| MySQL connection limit | | | |
| Celery worker crash | | | |
| Webhook delivery fail | | | |
| DB migration error | | | |

## Communication Templates

### P1 - Initial (within 30 min)
```
Subject: [P1 Incident] Service Impact - {Tenant} - INC-{ID}

We are experiencing a service-impacting issue.
- Incident ID: INC-{ID}
- Start time: {time}
- Affected service: {service}
- Impact: {description}
- We are actively investigating.
- Next update: in 30 minutes
```

### P1 - Resolved
```
Subject: [RESOLVED] INC-{ID} - Service Restored

The service has been restored.
- Incident ID: INC-{ID}
- Duration: {duration}
- Root cause: {brief}
- A postmortem will be shared within 48 hours.
```

### P2 - Initial (within 2 hours)
```
Subject: [P2] Issue Detected - {Service} - INC-{ID}

We have detected an issue with {service}.
- Incident ID: INC-{ID}
- Impact: {description}
- Workaround: {if available}
- Expected resolution: {ETA}
```
