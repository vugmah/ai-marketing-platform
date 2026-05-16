# Pilot Customer Onboarding Checklist

## Pre-Onboarding (Platform Team)
- [ ] Staging environment up: `docker compose -f docker-compose.staging.yml ps`
- [ ] MySQL migrations current: `alembic current` shows `009`
- [ ] Celery workers running: `docker logs aimp_staging_celery --tail 20`
- [ ] Redis healthy: `redis-cli -p 6380 ping` returns `PONG`
- [ ] Smoke tests pass: `python scripts/staging_smoke_test.py --host http://localhost:8001`
- [ ] Feature flags configured for pilot cohort
- [ ] Alerting rules active in Prometheus
- [ ] Runbook printed and on-call roster confirmed

## Day 0: Account Setup
- [ ] Create company record
- [ ] Create admin user
- [ ] Configure branch(es)
- [ ] Set tenant resource quotas
- [ ] Set AI safety policies
- [ ] Verify RBAC roles assigned
- [ ] Send welcome email with login credentials

## Day 1: ERP Connection
- [ ] Guide customer to ERP settings page
- [ ] Collect ERP endpoint + credentials
- [ ] Test ERP sync (manual trigger)
- [ ] Verify menu/products imported
- [ ] Verify inventory data correct
- [ ] Document any ERP-specific issues

## Day 2: Social & WhatsApp
- [ ] Connect Instagram account
- [ ] Connect Meta Ads (if applicable)
- [ ] Configure WhatsApp Business API
- [ ] Test incoming message webhook
- [ ] Verify AI auto-reply triggers
- [ ] Test escalation to human operator

## Day 3: First Campaign
- [ ] Create first campaign (AI-assisted)
- [ ] Set budget and targeting
- [ ] Approve AI-generated creative
- [ ] Publish campaign
- [ ] Monitor real-time metrics
- [ ] Verify follower analytics updating

## Day 4-7: Monitoring
- [ ] Daily health check via `scripts/staging_health_check.py`
- [ ] Review AI hallucination scores
- [ ] Check tenant resource usage
- [ ] Review support tickets (if any)
- [ ] Collect customer feedback
- [ ] Document friction points

## Week 2: Scale Decision
- [ ] All smoke tests still passing
- [ ] No P1/P2 incidents
- [ ] Customer NPS >= 7
- [ ] AI safety scores acceptable
- [ ] Resource usage within quotas
- [ ] **DECISION: Expand to next cohort or abort**
