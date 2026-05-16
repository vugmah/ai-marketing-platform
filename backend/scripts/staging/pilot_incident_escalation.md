# Pilot Incident Escalation Flow

## Severity Matrix

| Severity | Definition | Response Time | Escalation |
|----------|-----------|---------------|------------|
| P1-Critical | Data loss, security breach, complete outage | 15 min | Auto-escalate to on-call engineer |
| P2-High | Major feature broken, performance severely degraded | 1 hour | Escalate if unresolved in 30 min |
| P3-Medium | Feature partially broken, workaround exists | 4 hours | Escalate if unresolved in 2 hours |
| P4-Low | Cosmetic issue, documentation gap | 24 hours | No automatic escalation |

## Escalation Chain

```
P4 (Low)          -> L1 Support
                    |
P3 (Medium)       -> L1 Support -> L2 Technical (if unresolved)
                    |
P2 (High)         -> L1 Support -> L2 Technical -> L3 Engineering
                    |                 |
                    |                 +-> Customer communication
                    |
P1 (Critical)     -> On-Call Engineer + Engineering Lead + Product
                    |
                    +-> Customer communication (within 30 min)
                    +-> Postmortem scheduled within 48 hours
```

## Escalation Contacts

| Role | Contact Method | Availability |
|------|---------------|--------------|
| L1 Support | Slack #pilot-support | Business hours |
| L2 Technical | Slack #pilot-tech-escalation | Business hours + on-call |
| L3 Engineering | PagerDuty / phone | 24/7 on-call rotation |
| Product Manager | Slack #pilot-ops | Business hours |

## Pilot-Specific Rules

1. **All P1 incidents** trigger automatic customer communication within 30 minutes
2. **Data loss of any kind** = automatic P1 regardless of tenant size
3. **AI safety violations** = P2 minimum, P1 if customer-facing
4. **ERP sync failures** = P2 if affecting customer operations
5. **Webhook delivery failures** > 10% = P2
6. **Queue depth** > 1000 for > 5 min = P2

## Rollback Triggers

| Condition | Action | Time Limit |
|-----------|--------|------------|
| P1 incident + customer impact | Immediate rollback | 15 min |
| > 3 P2 incidents in 24h | Scheduled rollback | 2 hours |
| AI safety violation confirmed | Disable AI features for tenant | 5 min |
| Data integrity issue | Pause writes, investigate | Immediate |

## Communication Templates

### P1 Initial Communication (within 30 min)
```
Subject: [P1] Service Impact - {Tenant Name} - {Incident ID}

We are investigating a service-impacting issue affecting your account.
Incident ID: {id}
Start time: {timestamp}
Impact: {description}
ETA for update: 30 minutes
```

### Resolution Communication
```
Subject: [RESOLVED] {Incident ID} - Service Restored

The issue has been resolved.
Incident ID: {id}
Duration: {duration}
Root cause: {summary}
Next steps: {postmortem_date}
```
