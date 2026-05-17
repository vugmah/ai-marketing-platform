# AI Marketing Platform v2.0 - Pilot Staging Baseline

> **DONOT MODIFY THIS FILE** - This is the rollback reference point.
> Created: 2026-05-18

---

## 1. Baseline Identity

| Property | Value |
|----------|-------|
| **Tag** | `pilot-staging-stable` |
| **Commit** | `1331a91` |
| **Date** | 2026-05-18 03:15 UTC+8 |
| **Status** | HEALTHY |
| **Frontend URL** | https://q75ithfbjdmro.kimi.page |
| **Backend Status** | LIVE (Railway) |

---

## 2. Frontend Build Artifact

| Property | Value |
|----------|-------|
| **CSS Asset** | `index-CwWckJBW.css` (108.64 kB / gzip: 18.08 kB) |
| **JS Asset** | `index-jRI4YMSM.js` (1,101.24 kB / gzip: 286.80 kB) |
| **Entry** | `dist/index.html` |

### Included in this build:
- Mobile responsive sidebar fix (hidden by default < 768px)
- Drawer overlay on mobile hamburger open
- Auto-close sidebar on navigation
- Content full width on mobile
- overflow-x-hidden protection
- Bottom navigation bar on mobile
- Touch-friendly tap targets (44px min)

---

## 3. Backend Feature Flags (26 Modules)

### ACTIVE (13 modules - default true or enabled)

| # | Module | Flag | Status | Endpoint Prefix |
|---|--------|------|--------|-----------------|
| 1 | health | `ENABLE_HEALTH=true` | ON | `/api/v2/health/*` |
| 2 | auth | `ENABLE_AUTH=true` | ON | `/api/v2/auth/*` |
| 3 | followers | `ENABLE_FOLLOWERS=true` | ON | `/api/v2/followers/*` |
| 4 | companies | `ENABLE_COMPANIES=true` | ON | `/api/v2/companies/*` |
| 5 | branches | `ENABLE_BRANCHES=true` | ON | `/api/v2/branches/*` |
| 6 | dashboard | `ENABLE_DASHBOARD=true` | ON | `/api/v2/dashboard/*` |
| 7 | analytics | `ENABLE_ANALYTICS=true` | ON | `/api/v2/analytics/*` |
| 8 | media | `ENABLE_MEDIA=true` | ON | `/api/v2/media/*` |
| 9 | billing | `ENABLE_BILLING=true` | ON | `/api/v2/billing/*` |
| 10 | ads | `ENABLE_ADS=true` | ON | `/api/v2/ads/*` |
| 11 | reports | `ENABLE_REPORTS=true` | ON | `/api/v2/reports/*` |
| 12 | support | `ENABLE_SUPPORT=true` | ON | `/api/v2/support/*` |
| 13 | governance | `ENABLE_GOVERNANCE=true` | ON | `/api/v2/governance/*` |
| 14 | realtime | `ENABLE_REALTIME=true` | ON | `/api/v2/realtime/*` |

### DISABLED (11 modules - false)

| # | Module | Flag | Status | Notes |
|---|--------|------|--------|-------|
| 1 | erp | `ENABLE_ERP=true` | ENABLED* | *In code but load_router may skip if import fails |
| 2 | notifications | `ENABLE_NOTIFICATIONS=false` | OFF | Next: Step 5 |
| 3 | ai | `ENABLE_AI=false` | OFF | Next: Step 7 |
| 4 | rag | `ENABLE_RAG=false` | OFF | Next: Step 8 |
| 5 | social | `ENABLE_SOCIAL=false` | OFF | Next: Step 6 |
| 6 | events | `ENABLE_EVENTS=false` | OFF | TBD |
| 7 | audit | `ENABLE_AUDIT=false` | OFF | TBD |
| 8 | knowledge | `ENABLE_KNOWLEDGE=false` | OFF | TBD |
| 9 | localization | `ENABLE_LOCALIZATION=false` | OFF | Next: Step 9 |
| 10 | revenue | `ENABLE_REVENUE=false` | OFF | Next: Step 10 |

### Special Handling
- `governance`: Direct `if MODULE_FLAGS.get("governance")` check (lines 335-337)
- `localization`: Direct `if MODULE_FLAGS.get("localization")` check (lines 344-346)
- `revenue`: Direct `if MODULE_FLAGS.get("revenue")` check (lines 353-355)
- `realtime`: Direct `if MODULE_FLAGS.get("realtime")` check (lines 362-367)

---

## 4. Environment Configuration

### railway.toml
```toml
[build]
builder = "DOCKERFILE"
dockerfilePath = "backend/Dockerfile"

[deploy]
healthcheckPath = "/api/v2/health/live"

[deploy.env]
PORT = "8080"
LOG_LEVEL = "INFO"
ENVIRONMENT = "staging"
```

### Dockerfile Key Points
- Base: `python:3.12-slim`
- Node.js 20.x (for frontend build)
- Builder pattern: backend first, then full COPY
- User: `aimp` (uid 1000, gid 1000)
- Healthcheck: `/api/v2/health/live`
- Workers: 2 (uvicorn)

### Key Env Vars (from code analysis)
| Variable | Default | Purpose |
|----------|---------|---------|
| PORT | 8080 | Server port |
| LOG_LEVEL | INFO | Logging level |
| ENVIRONMENT | staging | Runtime environment |
| DATABASE_URL | - | MySQL connection |
| REDIS_URL | - | Redis/Celery |
| STORAGE_PROVIDER | disabled | File storage |
| JWT_SECRET_KEY | auto-generate | Token signing |
| SECRET_KEY | auto-generate | Encryption key |

---

## 5. Module Activation Queue

Planned rollout order. Each step = one module only.

```
Step 0: mobile-responsive-fix      DONE (in 1331a91)
Step 1: governance-advanced        ENABLED (was already true)
Step 2: reports                    ENABLED (was already true)
Step 3: analytics-advanced         ENABLED (was already true)
Step 4: notifications              FLAG: false -> ENABLE_NOTIFICATIONS=true
Step 5: social-advanced            FLAG: false -> ENABLE_SOCIAL=true
Step 6: ai                         FLAG: false -> ENABLE_AI=true
Step 7: rag                        FLAG: false -> ENABLE_RAG=true
Step 8: localization               FLAG: false -> ENABLE_LOCALIZATION=true
Step 9: revenue                    FLAG: false -> ENABLE_REVENUE=true
Step 10: erp-activation            Verify ERP loads correctly
Step 11: events                    FLAG: false -> ENABLE_EVENTS=true
Step 12: audit                     FLAG: false -> ENABLE_AUDIT=true
Step 13: knowledge                 FLAG: false -> ENABLE_KNOWLEDGE=true
```

**Note:** Steps 1-3 already enabled in baseline. Real work starts at Step 4 (notifications).

---

## 6. Health Check Endpoints

| Endpoint | Expected | Method |
|----------|----------|--------|
| `GET /api/v2/health/live` | `{"status":"healthy"}` | Liveness |
| `GET /api/v2/health/ready` | `{"status":"healthy","checks":{...}}` | Readiness |
| `GET /api/v2/health/db` | `{"status":"healthy","message":"Database connected"}` | DB check |
| `GET /api/v2/health/redis` | `{"status":"healthy",...}` | Redis check |

---

## 7. ROLLBACK PROCEDURES

### A. Frontend Rollback (kimi.page)

```bash
# To rollback to this baseline:
cd /mnt/agents/output/app
git reset --hard pilot-staging-stable
npm run build
# Deploy dist/ folder again
```

### B. Backend Rollback (Railway)

```bash
# Option 1: Via Railway CLI
railway up --detach
railway rollback <deployment-id>

# Option 2: Via Git
git checkout pilot-staging-stable
git push --force-with-lease

# Option 3: Via Railway Dashboard
# Deployments -> Select this deploy -> Redeploy
```

### C. Feature Flag Emergency Off

For any module, set env var to false in Railway Dashboard:
```
ENABLE_<MODULE>=false
```
Then restart the service.

### D. Full System Rollback

```bash
# 1. Frontend
cd /mnt/agents/output/app
git reset --hard pilot-staging-stable
npm run build
# Deploy dist/

# 2. Backend
git push origin pilot-staging-stable:main --force-with-lease
# Railway auto-deploys from main branch
```

---

## 8. Module Activation Procedure (Per Module)

For each module in the queue:

```bash
# 1. Enable flag in main.py
grep 'ENABLE_MODULE="false"' backend/app/main.py
# Change to "true"

# 2. Check for import errors
grep "from app.module" backend/app/*.py backend/app/**/*.py

# 3. Build frontend (if needed)
npm run build

# 4. Commit
git add -A
git commit -m "feat: enable MODULE module"

# 5. Push
git push

# 6. Deploy
railway up

# 7. Test
# - /api/v2/health/live  -> 200
# - /api/v2/health/ready -> 200
# - /api/v2/health/db    -> 200
# - Module endpoint      -> 200

# 8. Check logs
railway logs -f
# Look for: [FEATURE FLAG] MODULE: ENABLED
# No: [FEATURE FLAG] MODULE: ENABLED but import failed

# 9. If failure:
#   a. Set ENABLE_MODULE=false in Railway Dashboard -> Restart
#   b. OR: git revert HEAD -> git push
#   c. Re-test health endpoints
```

---

## 9. Known Limitations at Baseline

| # | Limitation | Impact | Workaround |
|---|------------|--------|------------|
| 1 | JWT_SECRET_KEY auto-generated | Tokens invalidated on restart | Set env var in Railway |
| 2 | SECRET_KEY auto-generated | Encryption keys change on restart | Set env var in Railway |
| 3 | STORAGE_PROVIDER=disabled | File uploads don't work | Set to s3/r2 with credentials |
| 4 | MySQL connection logs at INFO | Log noise | Set LOG_LEVEL=WARNING |
| 5 | 11 modules disabled | Reduced functionality | Activate per queue |
| 6 | Chunk size > 500KB warning | Slower initial load | Code splitting needed |

---

## 10. Commit History at Baseline

```
1331a91 fix: Mobile responsive sidebar + layout                    <- HEAD
73707f4 Fix MySQL Railway connection + auto-generate secrets
53d8135 fix: Railway build - auto-patch mockSocialAccounts
470cce8 Fix: mockSocialAccounts runtime error
f91452f fix: Railway deploy - remove --force flag from vite build
d417b57 Test: empty commit to verify Railway deploy pipeline
47d573d fix: Dockerfile vite build --force to clear cache
aa14cc5 fix: Dockerfile COPY order - frontend before backend
```

---

*End of Baseline Document*
*Do not modify. Create a new file for updates.*
