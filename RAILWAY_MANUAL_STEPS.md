# Railway Dashboard Manual Steps

## Onemli: Railway API token suresi dolmustur. Asagidaki adimlar Railway Dashboard uzerinden manuel olarak yapilmalidir.

---

## Adim 1: STORAGE_PROVIDER Duzelt

1. https://railway.com/project/17b41d5d-0bb0-44ab-be45-4c93f0d00406 adresine git
2. "ai-marketing-platform" servisine tikla
3. "Variables" sekmesine tikla
4. `STORAGE_PROVIDER` degiskenini bul
5. Degerini `local` yerine `disabled` yap
6. Auto-deploy otomatik baslayacaktir

**Neden:** Config validation staging'de `local` yasakliyor. `disabled` = media upload kapali, pilot staging icin guvenli.

---

## Adim 2: Redis Servisi Ekle

1. Ayni proje sayfasinda: "New" butonuna tikla
2. "Database" > "Redis" sec
3. Redis servisi otomatik olusturulacak
4. Backend servisine `REDIS_URL` otomatik atanacak

**Neden:** Celery worker + beat Redis gerektirir. Queue islemleri icin zorunlu.

---

## Adim 3: Deploy'i Izle

1. "Deployments" sekmesine tikla
2. Son deploy'in status'u "Building" > "Deploying" > "Healthy" olmali
3. Loglar'i tikla, runtime loglari izle

---

## Adim 4: Health Endpoint Testi (Deploy Sonrasi)

Asagidaki endpoint'leri tarayici veya curl ile test et:

```bash
# Live probe (hafif - DB/Redis check yok)
curl https://ai-marketing-platform-production-c674.up.railway.app/api/v2/health/live
# Beklenen: {"status": "ok"}

# Ready probe (DB + Redis check)
curl https://ai-marketing-platform-production-c674.up.railway.app/api/v2/health/ready
# Beklenen: {"status": "ok"}

# DB check
curl https://ai-marketing-platform-production-c674.up.railway.app/api/v2/health/db
# Beklenen: {"status": "ok"}

# Redis check
curl https://ai-marketing-platform-production-c674.up.railway.app/api/v2/health/redis
# Beklenen: {"status": "ok"}

# OpenAPI schema
curl https://ai-marketing-platform-production-c674.up.railway.app/api/openapi.json
# Beklenen: 200, JSON response
```

---

## Adim 5: Migration Kontrolu

Railway Console veya Deployments > Shell:

```bash
cd backend && python -m alembic current
# Beklenen: head (010 migration)

cd backend && python -m alembic history
# Beklenen: 10 migration listesi
```

---

## Adim 6: Celery Worker Ekle (Istege Bagli)

Ayni projede yeni bir servis olarak Celery worker eklenebilir:

1. "New" > "Empty Service"
2. Source: Ayni Git repo
3. Start Command: `cd backend && celery -A app.celery_app worker --loglevel=info`
4. Environment: Ayni env (REDIS_URL otomatik gelir)

Beat icin ayri bir servis:
1. Start Command: `cd backend && celery -A app.celery_app beat --loglevel=info`

---

## Onceden Yapilanlar (Sizin Tarafinizdan)

| Adim | Durum |
|------|-------|
| Railway proje olusturma | Mevcut (Marketing ai) |
| MySQL 8 ekleme | Mevcut (Online) |
| JWT_SECRET_KEY ekleme | Mevcut |
| SECRET_KEY ekleme | Mevcut |
| ENVIRONMENT=staging | Mevcut |
| AI_SUPERVISED_MODE=true | Mevcut |

---

## Kod Tarafinda Yapilanlar (Bizim Tarafimizdan)

| Degisiklik | Durum |
|------------|-------|
| Dockerfile CMD override kaldirildi | Backend/Dockerfile temiz |
| Config validation aktif | Staging'de local yasak |
| PyJWT, numpy, structlog + 10 diger paket | requirements.txt'e eklendi |
| 10 import hatasi duzeltildi | auth/jwt.py, permissions.py, roles.py, social/router.py, social/service.py |
| Dockerfile DOCKERFILE builder | railway.toml duzgun |

---

## Beklenen Hatalar

Eger deploy sonrasi yeni hata olursa, loglarda su anahtar kelimeleri ara:
- `ModuleNotFoundError` -> Eksik pip paketi
- `pydantic.ValidationError` -> Config hatasi (env eksik)
- `sqlalchemy` -> DB baglanti hatasi
- `redis` -> Redis baglanti hatasi

Yeni hatayi tam log ile paylasin, hemen cozeriz.
