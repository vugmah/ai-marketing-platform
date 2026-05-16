# Railway 2 Adim Rehberi

## Problem
Backend crash nedeni: STORAGE_PROVIDER=local, ama staging'de local yasak.
Cozum: 2 adim.

---

## Adim 1: STORAGE_PROVIDER Duzelt (30 saniye)

1. https://railway.com/project/17b41d5d-0bb0-44ab-be45-4c93f0d00406
2. "ai-marketing-platform" servisine tikla
3. "Variables" sekmesi
4. STORAGE_PROVIDER satirini bul
5. Degeri `disabled` yap
6. Kaydet (auto-deploy baslar)

---

## Adim 2: Redis Ekle (30 saniye)

1. Ayni sayfada "New" butonu
2. "Database" > "Redis"
3. Otomatik eklenir, REDIS_URL backend'e atanir

---

## Beklenen Sonuc (2-3 dakika icinde)

1. Deployments sekmesinde yeni build
2. Status: Building > Deploying > Healthy
3. Health endpoint test:
```bash
curl https://ai-marketing-platform-production-c674.up.railway.app/api/v2/health/live
# {"status": "ok"}

curl https://ai-marketing-platform-production-c674.up.railway.app/api/v2/health/ready
# {"status": "ok"}
```

---

## Hata Olursa

Terminalde bu komutu calistir, tam logu gonder:
```bash
export RAILWAY_TOKEN=TOKENINIZ
npx --yes @railway/cli@4.58.0 logs --service 20c0d48f-7bae-4de0-ad49-54f62c3b2a26
```
