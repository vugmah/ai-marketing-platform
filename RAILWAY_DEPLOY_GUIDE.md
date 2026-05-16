# Railway Deployment Guide - AI Marketing Platform v2.0

Bu rehber Railway'e MySQL 8 + Redis ile deploy adimlarini anlatir.
SQLite KESINLIKLE kullanilmaz.

---

## 1. Oncelikler

| Gereksinim | Surum | Neden |
|------------|-------|-------|
| Railway CLI | latest | Deploy ve yonetim |
| Railway hesabi | - | Uye ol ve odeme yontemi ekle |
| Railway proje | - | Servisleri gruplar |

## 2. Kurulum

```bash
# Railway CLI yukle
npm install -g @railway/cli

# Giris yap
railway login

# Proje olustur
railway init --name aimp-staging

# Proje sec
railway link
```

## 3. MySQL 8 Servisi Ekle

```bash
# MySQL 8 servisi ekle
railway add --database mysql

# MySQL 8 surumunu ayarla (Railway varsayilan olarak MySQL 8 verir)
# Railway otomatik olarak DATABASE_URL cevre degiskenini olusturur:
# DATABASE_URL=mysql+aiomysql://user:pass@host:3306/aimp

# MySQL baglantisini kontrol et
railway status
```

**Railway'in otomatik olusturdugu cevre degiskenleri:**
| Degisken | Ornek |
|----------|-------|
| DATABASE_URL | mysql://user:pass@mysql.railway.internal:3306/railway |
| MYSQLHOST | mysql.railway.internal |
| MYSQLPORT | 3306 |
| MYSQLUSER | railway |
| MYSQLPASSWORD | auto-generated |
| MYSQL_DATABASE | railway |

**Onemli:** Backend'in MySQL async driver'i `mysql+aiomysql` gerektirir. Railway'in verecegi DATABASE_URL'i async formata cevirmek gerekebilir. Bunu `railway.toml` veya backend config'inde hallet.

## 4. Redis Servisi Ekle

```bash
# Redis servisi ekle
railway add --database redis

# Redis baglantisini kontrol et
railway status
```

**Railway'in otomatik olusturdugu cevre degiskenleri:**
| Degisken | Ornek |
|----------|-------|
| REDIS_URL | redis://default:pass@redis.railway.internal:6379 |
| REDISHOST | redis.railway.internal |
| REDISPORT | 6379 |
| REDISUSER | default |
| REDISPASSWORD | auto-generated |

## 5. Cevre Degiskenlerini Ayarla

```bash
# Temel config
railway variables set ENVIRONMENT=staging
railway variables set DEBUG=false
railway variables set PORT=8000

# JWT secrets ( guclu secret uret )
railway variables set JWT_SECRET_KEY="$(openssl rand -base64 32)"
railway variables set SECRET_KEY="$(openssl rand -base64 32)"

# AI config
railway variables set ENABLE_AI_SAFETY=true
railway variables set ENABLE_TENANT_GOVERNANCE=true
railway variables set ENABLE_OBSERVABILITY=true
railway variables set ENABLE_COMPLIANCE_LOGGING=true
railway variables set AI_SUPERVISED_MODE=true

# Storage (MinIO yerine Railway Volume veya S3)
railway variables set STORAGE_PROVIDER=r2

# CORS
railway variables set CORS_ORIGINS="https://aimp-staging.up.railway.app"

# Tumu listele
railway variables
```

**Onemli:** DATABASE_URL Railway tarafindan otomatik atanir. Eger async driver formati farkliysa, ayri bir `ASYNC_DATABASE_URL` degiskeni ayarla:

```bash
# Async MySQL URL ayarla
railway variables set ASYNC_DATABASE_URL="mysql+aiomysql://$(railway variables get MYSQLUSER):$(railway variables get MYSQLPASSWORD)@$(railway variables get MYSQLHOST):$(railway variables get MYSQLPORT)/$(railway variables get MYSQL_DATABASE)"
```

## 6. Deploy Et

### 6a. Nixpacks ile (Onerilen)

```bash
# Railway'e deploy et
railway up

# Release phase otomatik calisir: alembic upgrade head
# Bu migration'lari gercek MySQL 8 uzerinde calistirir
```

### 6b. Dockerfile ile

```bash
# Railway.toml zaten Dockerfile builder olarak ayarli
railway up
```

### 6c. Procfile ile

Procfile su process'leri tanimlar:
- **web:** FastAPI backend (2 worker)
- **worker:** Celery worker (concurrency=2)
- **beat:** Celery beat (periodic tasks)
- **release:** Alembic migration (`upgrade head`)

Railway otomatik olarak `release` phase'i deploy oncesi calistirir.

## 7. Deploy Sonrasi Kontroller

```bash
# Deploy durumunu kontrol et
railway status

# Loglari izle
railway logs

# Health check
railway run -- curl -s https://$RAILWAY_PUBLIC_DOMAIN/api/v2/health/live
railway run -- curl -s https://$RAILWAY_PUBLIC_DOMAIN/api/v2/health/ready

# Migration durumu
railway run -- alembic current

# DB tablolarini kontrol et
railway run -- python -c "
from sqlalchemy import create_engine, inspect
from app.config import settings
engine = create_engine(settings.DATABASE_URL.replace('mysql+aiomysql', 'mysql+pymysql'))
inspector = inspect(engine)
for table in inspector.get_table_names():
    cols = inspector.get_columns(table)
    print(f'{table}: {len(cols)} columns')
"
```

## 8. Health Endpoint'lerini Test Et

```bash
export API_URL="https://$(railway variables get RAILWAY_PUBLIC_DOMAIN)"

# Live probe
curl -s "$API_URL/api/v2/health/live" | python -m json.tool

# Ready probe
curl -s "$API_URL/api/v2/health/ready" | python -m json.tool

# DB connectivity
curl -s "$API_URL/api/v2/health/db" | python -m json.tool

# Redis connectivity
curl -s "$API_URL/api/v2/health/redis" | python -m json.tool

# Metrics (Prometheus)
curl -s "$API_URL/api/v2/health/metrics" | head -20

# Detailed health
curl -s "$API_URL/api/v2/health/detailed" | python -m json.tool
```

## 9. Celery Worker'i Dogrula

```bash
# Worker durumunu kontrol et
railway logs --service worker

# Worker ping
railway run -- celery -A app.celery_app inspect ping

# Aktif task'lari listele
railway run -- celery -A app.celery_app inspect active

# Queue uzunlugunu kontrol et
railway run -- celery -A app.celery_app inspect reserved

# Beat scheduler'i kontrol et
railway logs --service beat
```

## 10. Pilot Tenant Olustur

```bash
# Tenant ekle (API ile)
curl -X POST "$API_URL/api/v2/companies" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{
    "name": "Pilot Alpha",
    "slug": "pilot-alpha",
    "plan": "pilot",
    "max_users": 5,
    "max_branches": 2,
    "ai_safety_mode": "supervised",
    "auto_send_enabled": false,
    "erp_write_enabled": false,
    "billing_enabled": false,
    "features": {
      "ai_chat": true,
      "ai_support": true,
      "analytics_dashboard": true,
      "follower_intelligence": true,
      "whatsapp_integration": true,
      "campaign_management": false,
      "erp_sync": true
    }
  }'

# 3 pilot tenant icin tekrarla (alpha, beta, gamma)
```

## 11. Smoke Test

```bash
#!/bin/bash
# smoke-test.sh - Railway uzerinde canli smoke test

API_URL="https://$(railway variables get RAILWAY_PUBLIC_DOMAIN)"

echo "=== SMOKE TEST ==="
echo "Target: $API_URL"

# 1. Health
echo -n "Health live: "
curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v2/health/live" && echo " OK" || echo " FAIL"

# 2. DB
echo -n "Health DB: "
curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v2/health/db" && echo " OK" || echo " FAIL"

# 3. Redis
echo -n "Health Redis: "
curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v2/health/redis" && echo " OK" || echo " FAIL"

# 4. Metrics
echo -n "Metrics: "
curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/v2/health/metrics" && echo " OK" || echo " FAIL"

# 5. OpenAPI
echo -n "OpenAPI: "
curl -s -o /dev/null -w "%{http_code}" "$API_URL/api/openapi.json" && echo " OK" || echo " FAIL"

echo "=== SMOKE TEST COMPLETE ==="
```

## 12. Monitoring Aktif Et

Railway uzerinde monitoring:

```bash
# Railway dashboard'dan log streaming
railway logs --follow

# Railway metrics (dashboard uzerinden)
# Railway dashboard > project > metrics

# Railway alerting (dashboard uzerinden)
# Railway dashboard > project > alerts
```

**Not:** Prometheus ve Grafana Railway'de yerel servis olarak calismaz. Bunun yerine:
- Railway'in built-in monitoring'ini kullan
- Veya Datadog/New Relic gibi 3rd-party monitoring ekle

## 13. Rollback

```bash
# Onceki deploy'a don
railway rollback

# Belirli bir deploy'a don
railway rollback --deployment <deployment-id>

# Deploy listesi
railway history
```

## 14. Environment Degiskenleri Referansi

| Degisken | Zorunlu | Varsayilan | Aciklama |
|----------|---------|------------|----------|
| DATABASE_URL | Auto | - | Railway MySQL 8 URL |
| REDIS_URL | Auto | - | Railway Redis URL |
| JWT_SECRET_KEY | Yes | - | 32+ karakter |
| SECRET_KEY | Yes | - | 32+ karakter, JWT'den farkli |
| ENVIRONMENT | Yes | staging | staging/production |
| PORT | Auto | 8000 | Railway otomatik atar |
| AI_SUPERVISED_MODE | Yes | true | true/false |
| ENABLE_AI_SAFETY | Yes | true | true/false |
| STORAGE_PROVIDER | No | local | r2/local |

## 15. Hata Ayiklama

```bash
# Loglari gor
railway logs

# Belirli servis loglari
railway logs --service web
railway logs --service worker
railway logs --service beat

# Container icerisinde komut calistir
railway run -- bash

# Cevre degiskenlerini kontrol et
railway variables

# Deploy durumu
railway status
```

## Onemli Notlar

1. **SQLite KESINLIKLE kullanilmaz.** Tum veriler Railway MySQL 8'de.
2. **Redis KESINLIKLE gercek.** Railway Redis servisi.
3. **Migration'lar release phase'de otomatik.** `alembic upgrade head` Procfile'de.
4. **Celery worker + beat ayri servisler.** Railway bunlari ayri container'lar olarak calistirir.
5. **Health check Railway tarafindan izlenir.** `/api/v2/health/live` endpoint'i zaten mevcut.
6. **Zero-downtime deploy.** Railway rolling deploy yapar.
7. **SSL otomatik.** Railway otomatik HTTPS saglar.
