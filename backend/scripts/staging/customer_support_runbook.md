# Customer Support & Success Runbook

## Escalation Levels
| Level | Response Time | Owner | Trigger |
|-------|--------------|-------|---------|
| L1 | 15 min | Customer Success | General questions, onboarding help |
| L2 | 1 hour | Backend Engineer | API errors, sync failures, AI issues |
| L3 | 4 hours | Platform Lead | Data loss, security incident, outage |
| L4 | 24 hours | CTO | Multi-tenant breach, complete outage |

## Common Issues & Resolution

### Issue: "Cannot login"
1. Check if account exists in `users` table
2. Verify company is active
3. Check JWT token expiry
4. Reset password if needed
5. Escalate to L2 if DB connection issue

### Issue: "ERP sync failed"
1. Check ERP credentials in settings
2. Run manual sync via `/api/v2/erp/sync`
3. Check `erp_sync_logs` for errors
4. Verify ERP endpoint reachable
5. Escalate to L2 if API format mismatch

### Issue: "AI gave wrong answer"
1. Check `ai_hallucination_scores` for the conversation
2. If score > 0.3: flag for review
3. If unsafe content: trigger approval workflow
4. Document in moderation queue
5. Adjust AI safety policy if pattern detected

### Issue: "Campaign not publishing"
1. Check campaign status in DB
2. Verify ad account connected
3. Check platform API quota
4. Review Celery task queue
5. Escalate to L2 if platform API error

### Issue: "Follower data not updating"
1. Check last sync timestamp
2. Verify social account token valid
3. Run manual sync
4. Check rate limits
5. Escalate to L2 if token expired

## Weekly Review Checklist
- [ ] Review all P1/P2 incidents from the week
- [ ] Check AI hallucination score trends
- [ ] Review tenant resource usage peaks
- [ ] Collect customer feedback summaries
- [ ] Update onboarding checklist based on learnings
- [ ] File engineering tickets for recurring issues
