"""Pilot Rollout Plan

4 haftalik pilot rollout plani:
- Hafta 1: 3 musteri, temel ozellikler
- Hafta 2: Kampanya + creative studio
- Hafta 3: ERP sync + governance dashboards
- Hafta 4: Tam pilot ozellikler

Abort kriterleri:
- >3 P1 incident/hafta
- Veri kaybi
- Queue bozulmasi
- AI safety violation
- Redis saturation
- Webhook failure spike
- Spam-risk escalation

Usage: cd backend && python scripts/staging/pilot_rollout_plan.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


ROLLOUT_PLAN = {
    "version": "1.0",
    "created_at": "2026-05-16",
    "total_duration_weeks": 4,
    "pilot_customers": 3,

    "weeks": [
        {
            "week": 1,
            "name": "Temel Ozellikler",
            "start_date": "2026-05-19",
            "end_date": "2026-05-25",
            "customers": ["pilot_001", "pilot_002", "pilot_003"],
            "features": [
                "AI destek (chat + ticket)",
                "Analytics dashboard",
                "Raporlar (PDF/Excel export)",
                "WhatsApp destek",
                "Follower intelligence (okuma + analiz)",
                "Knowledge base erisimi",
                "Branch yonetimi",
            ],
            "new_customers": 3,
            "ai_cost_budget_usd": 30,
            "outreach_limit_per_customer": 10,
            "support_sla_hours": 4,
            "success_criteria": [
                "Tum 3 musteri onboard edildi",
                "AI support kullanimi basladi",
                "Analytics dashboard aktif",
                "0 P1 incident",
                "AI approval rate >70%",
            ],
            "abort_triggers": [
                ">1 P1 incident",
                "Onboard tamamlanamadi",
                "AI safety violation",
            ],
            "daily_checks": [
                "AI approval queue derinligi",
                "Tenant trust skoru",
                "Platform reputation",
                "Spam risk trend",
            ],
        },
        {
            "week": 2,
            "name": "Kampanya + Creative Studio",
            "start_date": "2026-05-26",
            "end_date": "2026-06-01",
            "customers": ["pilot_001", "pilot_002", "pilot_003"],
            "features": [
                "Kampanya yonetimi",
                "Creative studio (gorsel/video)",
                "AI onerileri (content + zamanlama)",
                "A/B test destegi",
                "Sosyal medya yayini",
                "Re-engagement onerileri",
            ],
            "new_customers": 0,
            "ai_cost_budget_usd": 45,
            "outreach_limit_per_customer": 15,
            "support_sla_hours": 4,
            "success_criteria": [
                "Kampanya olusturuldu",
                "Creative studio kullanildi",
                "AI onerileri kullanildi",
                "0 P1 incident",
                "Block rate <2%",
            ],
            "abort_triggers": [
                ">2 P1 incident (kumulatif)",
                "Block rate >5%",
                "Spam-risk escalation",
            ],
            "daily_checks": [
                "Kampanya etkinligi",
                "AI oneri kalitesi",
                "Block/report rate",
                "Fatigue score trend",
            ],
        },
        {
            "week": 3,
            "name": "ERP Sync + Governance Dashboards",
            "start_date": "2026-06-02",
            "end_date": "2026-06-08",
            "customers": ["pilot_001", "pilot_002", "pilot_003"],
            "features": [
                "ERP read-only senkronizasyon",
                "Governance dashboard (tenant health)",
                "Cross-platform reputation monitoring",
                "Trust score dashboard",
                "ROI analytics",
                "Cadence optimization",
            ],
            "new_customers": 0,
            "ai_cost_budget_usd": 35,
            "outreach_limit_per_customer": 20,
            "support_sla_hours": 4,
            "success_criteria": [
                "ERP sync calisiyor (read-only)",
                "Governance dashboard aktif",
                "Trust score monitoring calisiyor",
                "0 P1 incident",
                "ERP sync latency <5 sn",
            ],
            "abort_triggers": [
                ">3 P1 incident (kumulatif)",
                "ERP veri tutarsizligi",
                "Trust score <40 (herhangi tenant)",
            ],
            "daily_checks": [
                "ERP sync latency",
                "Trust score trend",
                "Cross-platform reputation",
                "Governance score",
            ],
        },
        {
            "week": 4,
            "name": "Tam Pilot Ozellikler",
            "start_date": "2026-06-09",
            "end_date": "2026-06-15",
            "customers": ["pilot_001", "pilot_002", "pilot_003"],
            "features": [
                "Tum pilot ozellikler",
                "Operator coaching aktif",
                "Fatigue detection + auto-cooldown",
                "Performance learning",
                "Rollout analytics",
                "Incident management",
                "Tenant governance tam",
            ],
            "new_customers": 0,
            "ai_cost_budget_usd": 40,
            "outreach_limit_per_customer": 25,
            "support_sla_hours": 4,
            "success_criteria": [
                "Tum 4 hafta basarili tamamlandi",
                "Governance maturity >75/100",
                "Operator override rate <30%",
                "0 P1 incident (hafta 4)",
                "Musteri memnuniyeti >4/5",
            ],
            "abort_triggers": [
                ">3 P1 incident (toplam)",
                "Governance maturity <50",
                "Operator override >80%",
                "Data loss",
            ],
            "daily_checks": [
                "Operator override rate",
                "Fatigue score distribution",
                "Governance maturity score",
                "Musteri memnuniyeti",
            ],
        },
    ],

    "abort_criteria": {
        "global": [
            {
                "criterion": ">3 P1 incident/hafta",
                "threshold": 3,
                "period": "weekly",
                "action": "Tum rollout DURDUR",
                "escalation": "L3",
            },
            {
                "criterion": "Veri kaybi",
                "threshold": 1,
                "period": "immediate",
                "action": "Tum servisleri DURDUR, DB restore",
                "escalation": "L3",
            },
            {
                "criterion": "Queue bozulmasi",
                "threshold": 1,
                "period": "immediate",
                "action": "Queue islemlerini DURDUR, replay",
                "escalation": "L2",
            },
            {
                "criterion": "AI safety violation",
                "threshold": 1,
                "period": "immediate",
                "action": "AI servisini KAPAT, manuel review",
                "escalation": "L2",
            },
            {
                "criterion": "Redis saturation",
                "threshold": 95,
                "period": "continuous",
                "action": "Redis FLUSH, servis restart",
                "escalation": "L2",
            },
            {
                "criterion": "Webhook failure spike",
                "threshold": 50,
                "period": "5min",
                "action": "Webhook islemlerini DURDUR",
                "escalation": "L2",
            },
            {
                "criterion": "Spam-risk escalation",
                "threshold": 0.7,
                "period": "continuous",
                "action": "Tenant outreach KISITLA",
                "escalation": "L2",
            },
            {
                "criterion": "Platform reputation <40",
                "threshold": 40,
                "period": "continuous",
                "action": "Platform outreach DURDUR",
                "escalation": "L2",
            },
        ],
    },

    "total_budget": {
        "ai_cost_usd": 150,
        "support_hours": 40,
        "incident_response_hours": 8,
    },
}


def main() -> int:
    print("=" * 70)
    print("  PILOT ROLLOUT PLAN")
    print(f"  Sure: {ROLLOUT_PLAN['total_duration_weeks']} hafta")
    print(f"  Pilot musteri: {ROLLOUT_PLAN['pilot_customers']}")
    print("=" * 70)

    for week in ROLLOUT_PLAN["weeks"]:
        print(f"\n{'=' * 70}")
        print(f"  Hafta {week['week']}: {week['name']}")
        print(f"  {week['start_date']} - {week['end_date']}")
        print(f"{'=' * 70}")

        print(f"\n  Musteriler: {', '.join(week['customers'])}")
        print(f"  Yeni musteri: {week['new_customers']}")
        print(f"  AI butcesi: ${week['ai_cost_budget_usd']}")
        print(f"  Outreach limit: {week['outreach_limit_per_customer']}/musteri")
        print(f"  Support SLA: {week['support_sla_hours']} saat")

        print(f"\n  Ozellikler:")
        for f in week["features"]:
            print(f"    - {f}")

        print(f"\n  Basari kriterleri:")
        for c in week["success_criteria"]:
            print(f"    [OK] {c}")

        print(f"\n  Abort tetikleyicileri:")
        for t in week["abort_triggers"]:
            print(f"    [ABORT] {t}")

        print(f"\n  Gunluk kontroller:")
        for c in week["daily_checks"]:
            print(f"    - {c}")

    print(f"\n{'=' * 70}")
    print("  GLOBAL ABORT KRITERLERI")
    print(f"{'=' * 70}")
    for criterion in ROLLOUT_PLAN["abort_criteria"]["global"]:
        print(f"\n  {criterion['criterion']}")
        print(f"    Threshold: {criterion['threshold']}")
        print(f"    Period: {criterion['period']}")
        print(f"    Aksiyon: {criterion['action']}")
        print(f"    Escalation: {criterion['escalation']}")

    print(f"\n{'=' * 70}")
    print("  BUTCE")
    print(f"{'=' * 70}")
    budget = ROLLOUT_PLAN["total_budget"]
    print(f"  AI maliyeti: ${budget['ai_cost_usd']}")
    print(f"  Support saati: {budget['support_hours']} saat")
    print(f"  Incident response: {budget['incident_response_hours']} saat")

    # Save plan
    output_path = PROJECT_ROOT / "scripts" / "staging" / "pilot_rollout_plan.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(ROLLOUT_PLAN, f, indent=2, ensure_ascii=False)

    print(f"\n  Plan kaydedildi: {output_path}")
    print(f"\n  DURUM: 4 haftalik rollout plani hazir")
    return 0


if __name__ == "__main__":
    sys.exit(main())
