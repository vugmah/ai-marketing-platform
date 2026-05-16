# Pilot Customer Onboarding Flow

## Day 0: Account Setup (0-2 hours)

### Step 1: Tenant Provisioning
- [ ] Create pilot tenant with isolated config
- [ ] Set feature flags (AI auto-send=OFF, ERP write=OFF)
- [ ] Configure rate limits (120 req/min, 30 AI req/min)
- [ ] Set AI quotas (100K tokens/hour, approval required for critical actions)
- [ ] Create admin user account
- [ ] Send welcome email with credentials

### Step 2: Initial Walkthrough
- [ ] Schedule 30-min onboarding call
- [ ] Share onboarding checklist
- [ ] Confirm primary contact
- [ ] Confirm branch count (max 2 for pilot)
- [ ] Confirm user count (max 5 for pilot)

## Day 1: Branch Setup (2-4 hours)

### Step 3: Branch Configuration
```
1. Navigate to Settings > Branches
2. Create first branch (main/headquarters)
   - Branch name
   - Address
   - Phone
   - Manager assignment
3. Create second branch if needed
4. Set branch-specific settings
```

### Step 4: Team Setup
```
1. Navigate to Settings > Users
2. Invite team members (max 4 additional)
3. Assign roles:
   - Admin (1-2 users)
   - Operator (2-3 users)
   - Viewer (optional)
4. Set branch assignments
5. Verify login works for all users
```

## Day 2: Channel Connections (2-4 hours)

### Step 5: WhatsApp Business Setup
```
1. Navigate to Social > WhatsApp
2. Click "Connect WhatsApp Business"
3. Scan QR code with WhatsApp Business app
4. Verify connection status = CONNECTED
5. Send test message
6. Test incoming message routing
```
**Common Issues**:
- QR code expires: Re-scan required
- Business account not verified: Submit verification documents
- Phone number already connected: Disconnect from other platform first

### Step 6: Instagram Connection
```
1. Navigate to Social > Instagram
2. Click "Connect Instagram"
3. Login with Instagram Business account
4. Grant required permissions
5. Select business account (not personal)
6. Verify follower count displays
```
**Common Issues**:
- Personal account: Must convert to Business/Creator
- Permissions denied: Re-auth with all permissions
- Account not found: Check Facebook Business Manager linking

### Step 7: Facebook Connection
```
1. Navigate to Social > Facebook
2. Click "Connect Facebook"
3. Login with Facebook
4. Select Facebook Page (not profile)
5. Grant Page permissions
6. Verify page data imports
```

## Day 3: ERP Integration (2-6 hours)

### Step 8: ERP Connection (Read-Only Mode)
```
1. Navigate to ERP > Settings
2. Select ERP type (Logo, Netsis, Mikro, or Custom)
3. Enter ERP connection details
   - Server address
   - Database name
   - Read-only credentials (IMPORTANT)
4. Test connection
5. Verify data sync (customers, products, sales)
6. Confirm NO WRITE ACCESS (pilot safety)
```
**Pilot Rule**: ERP connection is read-only. No write operations.

### Step 9: Data Validation
```
1. Check customer count matches ERP
2. Check product count matches ERP
3. Verify sales data imports correctly
4. Check date format compatibility
5. Verify currency handling
```

## Day 4: AI Knowledge Setup (2-3 hours)

### Step 10: Knowledge Ingestion
```
1. Navigate to AI > Knowledge Base
2. Upload company documents:
   - Product catalog (PDF/CSV)
   - FAQ document
   - Return policy
   - Pricing sheet
3. Wait for processing (may take 10-30 min)
4. Verify documents in knowledge base
5. Test AI with knowledge questions
```

### Step 11: AI Training Validation
```
1. Ask AI about company products
2. Verify answers reference uploaded documents
3. Check confidence scores (> 75% target)
4. Test edge cases (unknown products)
5. Confirm escalation works for low confidence
```

## Day 5: First Operational Flows (2-4 hours)

### Step 12: First Report Export
```
1. Navigate to Reports
2. Select report type (Sales Summary)
3. Set date range (last 7 days)
4. Choose format (Excel)
5. Generate report
6. Download and verify data
```

### Step 13: First AI Support Interaction
```
1. Navigate to AI Support
2. Ask a common customer question
3. Review AI response
4. Check confidence score
5. Approve or edit response
6. Send to customer (with approval)
```
**Pilot Rule**: All AI responses require operator approval.

### Step 14: First Campaign Creation
```
1. Navigate to Ads > Campaigns
2. Click "New Campaign"
3. Select platform (Facebook/Instagram)
4. Set budget (small: $50-100)
5. Define audience
6. Create ad creative
7. Save as DRAFT (do not publish yet)
8. Review with support team
```

## Day 6-7: Review & Optimization

### Step 15: Weekly Review
- [ ] Review all onboarded features
- [ ] Check AI quality scores
- [ ] Review support tickets
- [ ] Confirm all integrations stable
- [ ] Document feedback

### Completion Criteria
| Checkpoint | Required |
|-----------|----------|
| Branch setup complete | Yes |
| At least 1 social channel connected | Yes |
| ERP connected (read-only) | Yes |
| Knowledge base populated | Yes |
| First AI support interaction completed | Yes |
| First report generated | Yes |
| Team trained on core features | Yes |

### Onboarding Success Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Completion rate | > 80% | % of customers completing all steps |
| Average onboarding time | < 5 days | Days from account setup to completion |
| Support tickets during onboarding | < 3 per customer | Ticket count |
| Time stuck per step | < 2 hours | Average time blocked |

## Common Blockers & Solutions

| Blocker | Frequency | Solution |
|---------|-----------|----------|
| WhatsApp QR expires | 30% | Have customer ready before generating QR |
| Instagram not Business | 25% | Guide to convert account |
| ERP credentials wrong | 20% | Verify read-only access beforehand |
| Knowledge upload fails | 15% | Check file size (< 10MB) and format |
| AI confidence low | 10% | Add more training documents |
| User invite not received | 10% | Check spam folder, resend |
