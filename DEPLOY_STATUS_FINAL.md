# Deploy Durum Final Raporu

## Tarih: 2026-05-16

---

## Cozulen Bloklayici Hatalar

| # | Hata | Cozum |
|---|------|-------|
| 1 | railway.toml parse (restartPolicyType) | railway.json silindi |
| 2 | STORAGE_PROVIDER=local | Dockerfile override kaldirildi |
| 3 | PyJWT, numpy, structlog + 12 paket | requirements.txt'e eklendi |
| 4 | SocialMessageListResponse | SocialMessageResponse olarak duzeltildi |
| 5 | ConversationQueue | PublishingQueue olarak duzeltildi |
| 6 | auth/jwt.py yok | Olusturuldu |
| 7 | auth/permissions.py yok | Olusturuldu |
| 8 | auth/roles.py yok | Olusturuldu |
| 9 | decode_token | Alias eklendi |
| 10 | TokenData yok | Alias eklendi |
| 11 | get_db_session yok | Alias eklendi |
| 12 | get_company_id yok | Olusturuldu |
| 13 | get_optional_company_id yok | Olusturuldu |
| 14 | Optional import | Eklendi |
| 15 | VariantType enum eksik | Tamamlandi |
| 16 | VirusScanStatus + CLAMAV sabitleri | Eklendi |
| 17 | ads/schemas date field | metric_date olarak duzeltildi |

## Kalan Hatalar (Toplu Tespit)

Tarama sonucu 20+ modulde 100+ eksik sabit/fonksiyon:

| Modul | Eksik Sayisi |
|-------|-------------|
| app.exceptions | APIError |
| app.database | get_async_session, async_session_maker |
| app.ads.constants | 3 sabit |
| app.ai.constants | 40+ sabit |
| app.auth.jwt | get_current_user |
| app.auth.service | get_current_user_optional |
| app.billing.constants | 13 sabit |
| app.events.constants | 5 sabit |
| app.health.metrics | REGISTRY |
| app.media.constants | 4 sabit (CLAMAV) |
| app.reports.constants | 7 sabit |
| app.support.constants | 30+ sabit |

## Root Cause

Proje 228 Python dosyasi, 38 router, 100+ modul. 
Birçok constants.py dosyasi bos veya eksik.
Moduller birbirine tightly coupled.

## Cozum Onerisi

### Secenek 1: Lazy Import (Önerilen)
`main.py`'de tüm router'lari import etmek yerine,
healthy olan temel router'lari (health, auth, followers) aktif et,
digerlerini lazy import veya feature flag ile devre disi birak.

### Secenek 2: Sabitleri Tamamlama
Tüm constants.py dosyalarini eksiksiz doldurmak.
Tahmini: 50-100 eksik sabit.
Sure: 2-3 saat tek seferde odaklanarak.

### Secenek 3: Minimal App
Sadece health endpoint calisacak sekilde minimal main.py.
Sonra modul modul ekleme.

## Railway Durum
| Servis | Durum |
|--------|-------|
| MySQL 8 | Online |
| Redis | Eklendi |
| Backend | Crashed (import hatalari) |
| CLI Token | Read-only |

## Sonuc
Railway deploy altyapisi hazir. Build basarili.
Kalan sorun: Kod tabaninda eksik sabitler ve import'lar.
Toplu bir "constants tamamlama" session'i gerekiyor.
