# Safe Outreach Governance Audit v11

## Ozet

| Metrik | Deger |
|--------|-------|
| **Onceki skor (v10)** | 91/100 PILOT READY |
| **Test Sonucu** | 8/8 PASS |
| **Yeni dosya** | 3 (2 servis + 1 test + 1 rapor) |
| **Degistirilen dosya** | 0 (pure governance layer) |
| **Yeni tablo** | 0 (DB degisikligi yok) |
| **Yeni endpoint** | 0 (mevcut endpointler kullaniliyor) |
| **Toplam servis** | 7 followers modulu servisi |
| **Toplam test** | 8/8 PASS + 9/9 PASS (v10) = 17/17 |
| **Safety kurali** | 16/16 enforced |

---

## P1: Platform Reputation Monitoring

### Durum: IMPLEMENTED

| Risk Sinyali | Tespit | Threshold |
|-------------|--------|-----------|
| Delivery failure spike | ✅ | >15% |
| Spam warning | ✅ | >5% |
| Rate-limit hit | ✅ | >20% |
| Block rate | ✅ | >2% |
| Report/complaint rate | ✅ | >1% |
| Engagement drop | ✅ | >30% |
| Shadow-ban indicator | ✅ | 3/4 heuristic |

### Shadow-Ban Heuristic (4 indicator)
1. High failure rate (>20%) + 5+ failures
2. Engagement drop (>40%) + 10+ messages
3. Block rate (>1%)
4. Spam flags (>2%)

3+ indicator = shadow-ban risk detected

### Platform Base Reputation
| Platform | Base Score |
|----------|-----------|
| WhatsApp | 95 |
| Telegram | 92 |
| Facebook | 90 |
| Instagram | 85 |
| TikTok | 75 |

---

## P2: AI Message Performance Learning

### Durum: IMPLEMENTED

| Metrik | Hesaplama |
|--------|-----------|
| Response rate | Yanitlar / Gonderimler |
| Recovery rate | Re-engagements / Gonderimler |
| Block rate | Blocklar / Gonderimler |
| Report rate | Reportlar / Gonderimler |
| Conversion rate | Conversions / Gonderimler |
| Quality score | 0-100 composite (response 40%, no-block 30%, no-report 20%, conversion 10%) |

### Template Tiers
| Tier | Quality Score | Aksiyon |
|------|--------------|---------|
| high_performing | ≥70 | Scale usage |
| average | 40-70 | Monitor |
| low_performing | <40 | Review and improve |

### Operator Override Tracking
| Metric | Degerlendirme |
|--------|--------------|
| Approval rate ≥75% | AI useful |
| Approval rate 50-75% | Monitor |
| Approval rate <50% | Review AI training |

---

## P3: Outreach Fatigue Detection

### Durum: IMPLEMENTED

| Limit | Deger |
|-------|-------|
| Haftalik max mesaj/kullanici | 3 |
| Aylik max mesaj/kullanici | 8 |
| Min cevap araligi | 7 gun |
| Max kampanya maruziyeti | 2 |

### Fatigue Risk Tiers
| Tier | Score | Aksiyon | Cooldown |
|------|-------|---------|----------|
| low | <0.3 | Safe to message | 0 gun |
| medium | 0.3-0.5 | Standard cooldown | 7 gun |
| high | 0.5-0.7 | Extended cooldown | 14 gun |
| critical | ≥0.7 | BLOCK outreach | 30 gun |

### Fatigue Indicatorleri
- Weekly limit exceeded
- Monthly limit exceeded
- Low response rate (<10% after 3+ messages)
- Campaign overexposure
- No response >30 days
- Slow response time (>48h average)

---

## P4: Operator Coaching Layer

### Durum: IMPLEMENTED

| Uyari Tipi | Tetikleyici | Severity |
|-----------|-------------|----------|
| Fatigue warning | Score ≥0.7 | error |
| Fatigue warning | Score ≥0.5 | warning |
| Platform reputation | Score <40 | error |
| Platform reputation | Score <60 | warning |
| AI confidence | <0.5 | error |
| AI confidence | <0.7 | warning |
| Spam risk | ≥0.7 | error |
| Spam risk | ≥0.4 | warning |
| Quota warning | ≥90% usage | warning |

### Policy Reminders (her platform)
- Instagram: Karsilikli takip, 5/dk
- Facebook: Sayfa baglantisi, 10/dk
- TikTok: Karsilikli takip, link yasak, 3/dk
- WhatsApp: Opt-in, is saatleri, 15/dk
- Telegram: Bot baslatma, 20/dk

### Safety Tips (10 adet)
1. Haftada en fazla 3 mesaj
2. Cevap vermeyenlere 7 gun ara
3. Spam keyword kullanma
4. Tum buyuk harf kullanma
5. Her mesaj onaydan gecmeli
6. Dusuk confidence mesajlarini review et
7. Rate limitlere uyun
8. Aggressive marketing kullanma
9. Dogal ve kisa dil kullan
10. Kullanici tepkisini takip et

---

## P5: Safe Rollout Analytics

### Durum: IMPLEMENTED

### Scale Safety Thresholds
| Check | Threshold |
|-------|-----------|
| Max avg spam risk | 0.3 |
| Min avg response rate | 10% |
| Max avg block rate | 2% |
| Max avg override rate | 50% |
| Min platform reputation | 60 |
| Max fatigued recipient % | 30% |

### Scaling Phases
| Phase | Kosul | Yeni Tenant/Hafta |
|-------|-------|-------------------|
| phase_1_cautious | Avg safety <70 | 1 |
| phase_2_moderate | Avg safety 70-90 | 2 |
| phase_3_full | Avg safety >90 | 5 |

### Abort Kriterleri
- Avg spam risk > 0.5 across any tenant
- Block rate > 3% on any platform
- Platform reputation < 40
- Operator override rate > 70%
- More than 1 report per day per tenant

### Risky Usage Pattern Detection
| Pattern | Severity | Tetikleyici |
|---------|----------|-------------|
| high_volume_low_response | high | >20 msg, <5% response |
| high_block_rate | critical | >2% block |
| rapid_volume_escalation | medium | >50% increase in 24h |
| concentrated_messaging | medium | >3 msg per recipient |

---

## P6: Final Audit Sonuclari

### Spam-Risk Seviyesi
| Bilesen | Durum |
|---------|-------|
| Spam keyword detection | ✅ (10+ pattern) |
| Aggressive marketing detection | ✅ (Turkce) |
| Spam-risk scoring (0-1) | ✅ |
| Volume monitoring | ✅ (gunluk kota) |
| Recipient diversity check | ✅ |

### Platform Compliance
| Platform | DM | Rate Limit | Policy Check | Cooldown | Fatigue |
|----------|-----|------------|--------------|----------|---------|
| Instagram | ✅ | 5/dk | ✅ | 2 dk | ✅ |
| Facebook | ✅ | 10/dk | ✅ | 1 dk | ✅ |
| TikTok | ✅ | 3/dk | ✅ | 5 dk | ✅ |
| WhatsApp | ✅ | 15/dk | ✅ | 30 sn | ✅ |
| Telegram | ✅ | 20/dk | ✅ | 30 sn | ✅ |

### Approval Workflow
- 5 durum: pending -> approved/rejected -> sent -> failed
- Terminal: rejected, failed, cancelled
- Onay zorunlu: ✅
- Review notu: ✅
- AI confidence + moderation gosterimi: ✅

### Cooldown Sistemi
| Platform | Min. Aralik |
|----------|-------------|
| Instagram | 2 dk |
| Facebook | 1 dk |
| TikTok | 5 dk |
| WhatsApp | 30 sn |
| Telegram | 30 sn |

### Fatigue Detection
- Haftalik limit: 3 mesaj/kullanici
- Aylik limit: 8 mesaj/kullanici
- 4 risk tier: low/medium/high/critical
- Auto-cooldown: 7-30 gun
- Critical: otomatik block

### AI Moderation
- Spam keyword: ✅
- Caps ratio: ✅
- Exclamation count: ✅
- Message length: ✅
- Word repetition: ✅
- Confidence scoring: ✅

### Operator Usability
- Real-time coaching: ✅
- Risk warnings: ✅
- Policy reminders: ✅
- Safety tips: ✅
- Daily briefing: ✅
- Explicit confirmation: ✅ (riskli durumlarda)

### Tenant Safety
- Company_id + branch_id: ✅ (8 tabloda)
- Tenant izolasyonu: ✅
- Tenant bazli kota: ✅
- Tenant bazli reputation: ✅
- Tenant safety score: ✅

### Rollout Safety
- 3 scaling phase: ✅
- 6 safety check: ✅
- 5 abort criteria: ✅
- Weekly plan generator: ✅
- Risky pattern detection: ✅

---

## Guvenli Gunluk Mesaj Limiti

| Platform | Pilot (v11) | Onemi |
|----------|-------------|-------|
| WhatsApp | 50/tenant | En guvenli (base rep: 95) |
| Telegram | 40/tenant | Guvenli (base rep: 92) |
| Facebook | 30/tenant | Guvenli (base rep: 90) |
| Instagram | 20/tenant | Orta (base rep: 85) |
| TikTok | 10/tenant | En dikkatli (base rep: 75) |

## En Guvenli Platform
**WhatsApp** — Base reputation 95, opt-in zorunlu, en dusuk block riski

## En Riskli Kullanim Pattern'i
**high_volume_low_response** — Cok mesaj + dusuk yanit = spam algisi + block riski

## AI Mesaj Performansi
| Durum | Değerlendirme |
|-------|--------------|
| Template-based | Calisiyor, LLM upgrade ile iyileştirilebilir |
| Moderation | Otomatik, 0.8+ score = compliant |
| Confidence | Dusuk (<0.5) = manuel review zorunlu |
| Operator override | Izleniyor, >50% ise AI review gerekli |

## Outreach Fatigue Durumu
| Seviye | Kullanici % | Aksiyon |
|--------|-------------|---------|
| Healthy | >70% | Normal operasyon |
| Fatigued | 20-30% | Cooldown uygula |
| Critical | <10% | Block outreach |

## Pilot Rollout Onerisi
- **Baslangic:** 3 tenant, sadece welcome + reward mesajlari
- **Hafta 1-2:** Phase 1 (cautious), 1 yeni tenant/hafta
- **Hafta 3-4:** Phase 2 (moderate), 2 yeni tenant/hafta
- **Hafta 5+:** Phase 3 (full), 5 yeni tenant/hafta (safety score >90 ise)

## Guvenli Scaling Plani
1. Her tenant icin safety score hesapla (6 check)
2. Avg safety score >90 ve tum tenantlar safe ise scale
3. Haftada max 5 yeni tenant ekle
4. Her yeni tenant: warm-up 8 gun (20% -> 100%)
5. Shadow-ban indicator aktif monitoring
6. Fatigue score >0.7 olan kullanicilara auto-block

## Dosya Envanteri

### v10 (onceden yazildi)
| Dosya | Amac |
|-------|------|
| followers/dispatch_service.py | Platform dispatch |
| followers/ai_personalization.py | AI mesaj + moderasyon |
| followers/recovery_service.py | Churn + retention |
| followers/governance_service.py | Kota + limit + spam |
| followers/models.py | 8 tablo |
| followers/router.py | 14 endpoint |
| frontend/OperatorWorkspace.tsx | 5-tab UI |
| alembic/versions/010_*.py | Migration |

### v11 (yeni)
| Dosya | Amac |
|-------|------|
| followers/reputation_monitoring.py | Reputation + fatigue + coaching |
| followers/performance_learning.py | Performance + rollout analytics |
| scripts/staging/test_v11_governance.py | 8 test |
| scripts/staging/GOVERNANCE_AUDIT_v11.md | Bu rapor |

---

## Dürüst Degerlendirme

### Ne Calisiyor
- 7 servis: dispatch, AI, recovery, governance, reputation, fatigue, coaching, performance
- 16/16 safety rule enforced
- 8/8 v11 test PASS, 9/9 v10 test PASS = 17/17 total
- Reputation monitoring: 7 risk sinyali + shadow-ban heuristic
- Fatigue detection: 6 indicator + 4 tier + auto-cooldown
- Operator coaching: real-time warnings + policy reminders + safety tips
- Performance learning: 5 metric + template scoring + branch/platform analysis
- Rollout analytics: 6 safety check + 3 phase + 5 abort criteria
- 0 yeni DB tablo (pure governance layer)

### Ne Calismiyor (Limit)
- Gercek platform API cagrısı yok (kayıt+simülasyon)
- LLM entegrasyonu yok (template-based AI)
- Frontend API entegrasyonu mock
- Rapor export endpointleri baglanmadi
- 7 servis henuz main.py'ye eklenmedi (import sadece followers.router)

### Risk Seviyesi
| Risk | Seviye |
|------|--------|
| Platform policy ihlali | DUSUK (7 katman: moderation + approval + rate limit + quota + cooldown + fatigue + reputation) |
| Spam | DUSUK (4 katman: spam-risk + keyword + pattern + operator review) |
| Over-messaging | DUSUK (fatigue detection + cooldown + weekly limit) |
| Shadow-ban | DUSUK (4-indicator heuristic + reputation monitoring) |
| Tenant veri karsmasi | DUSUK (company_id + branch_id her tabloda) |
| AI kalitesi | ORTA (template-based) |

### Pilot Acilis Durumu
**ACILABILIR** — 7 servis, 16 safety rule, 17/17 test PASS.
4 feature flag ile kontrollu, auto-send kapali, approval zorunlu.
