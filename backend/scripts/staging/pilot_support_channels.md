# Pilot Support Channels

## Channel Structure

### Primary: Dedicated Slack Channel
- **Channel**: `#pilot-customer-{tenant_id}`
- **Access**: Customer team + AIMP L1/L2 support + Product
- **Purpose**: Day-to-day questions, quick issues, feedback
- **SLA**: 4 business hours response
- **Hours**: 09:00-18:00 local time

### Escalation: Technical Support
- **Channel**: `#pilot-tech-escalation`
- **Access**: L2 support + Engineering
- **Purpose**: Bugs, technical issues, integration problems
- **SLA**: 1 hour response
- **Hours**: Business hours + on-call for P1

### Emergency: PagerDuty
- **Trigger**: P1 incidents only
- **Escalation**: L3 engineering + product lead
- **Response**: 15 minutes
- **24/7**: Yes

### Async: Email
- **Address**: pilot-support@aimp.internal
- **Purpose**: Non-urgent questions, documentation requests
- **SLA**: 24 hours

## Support Process

### Level 1: Triage (0-30 minutes)
1. Acknowledge receipt
2. Classify severity (P1-P4)
3. Check if known issue
4. Provide workaround if available
5. Escalate if needed

### Level 2: Technical Resolution (30 min - 4 hours)
1. Reproduce issue
2. Check logs and metrics
3. Identify root cause
4. Implement fix or workaround
5. Communicate resolution

### Level 3: Engineering (4+ hours or P1)
1. Code-level investigation
2. Hotfix if needed
3. Postmortem for P1/P2
4. Permanent fix in next release

## Common Issue Categories

| Category | Frequency | Resolution Time | Escalation |
|----------|-----------|-----------------|------------|
| Onboarding questions | High | < 1 hour | L1 |
| WhatsApp connection | Medium | 2-4 hours | L2 |
| Instagram/Facebook auth | Medium | 2-4 hours | L2 |
| ERP sync issues | Medium | 4 hours | L2 |
| AI response quality | Medium | 1-2 hours | L2 |
| Report export failures | Low | 2 hours | L2 |
| Campaign publishing | Low | 1-2 hours | L2 |
| User permission issues | Low | 1 hour | L1 |
| Billing questions | N/A (pilot) | - | - |

## Weekly Review Template

### Pilot Customer Health Score
| Tenant | Health | Open Issues | AI Usage | Satisfaction |
|--------|--------|-------------|----------|--------------|
| pilot_001 | | | | |
| pilot_002 | | | | |
| pilot_003 | | | | |
| pilot_004 | | | | |
| pilot_005 | | | | |

### Metrics Review
- Onboarding completion rate: __%
- Average issue resolution time: __ hours
- P1/P2 incidents this week: __
- AI escalation rate: __%
- Customer satisfaction score: __/10

### Action Items
1. 
2. 
3. 

## Handoff Between Levels

### L1 -> L2
- Issue reproduced? Yes/No
- Logs attached? Yes/No
- Customer impact? Description
- Attempted workarounds: List

### L2 -> L3
- Root cause identified? Yes/No
- Hotfix possible? Yes/No
- Customer communication done? Yes/No
- Estimated fix time: __ hours
