"""Pilot Operations Tracking

Pilot operasyonlarini takip eder:
- Onboarding completion
- AI confidence
- Operator overrides
- Response rates
- Block/report rates
- Fatigue growth
- Tenant trust score
- Queue latency
- Support SLA
- Webhook reliability
- Rollout health

Usage: cd backend && python scripts/staging/pilot_operations_tracking.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


OPERATIONS_METRICS = {
    "onboarding": {
        "name": "Onboarding Completion",
        "description": "Pilot musterilerin onboarding tamamlama orani",
        "type": "percentage",
        "target": 100,
        "warning_threshold": 80,
        "critical_threshold": 50,
        "measurement": "Onboarding adimlarinin tamamlanma orani",
        "frequency": "daily",
    },
    "ai_confidence": {
        "name": "AI Confidence Score",
        "description": "AI mesajlarinin ortalama confidence skoru",
        "type": "float",
        "target": 0.8,
        "warning_threshold": 0.6,
        "critical_threshold": 0.5,
        "measurement": "AI onerilerinin confidence ortalamasi",
        "frequency": "realtime",
    },
    "operator_override_rate": {
        "name": "Operator Override Rate",
        "description": "Operator override orani (dusuk = iyi)",
        "type": "percentage",
        "target": 30,
        "warning_threshold": 50,
        "critical_threshold": 80,
        "measurement": "Onaylanan AI mesajlari / Toplam AI mesajlari",
        "frequency": "daily",
    },
    "response_rate": {
        "name": "Outreach Response Rate",
        "description": "Follower outreach yanit orani",
        "type": "percentage",
        "target": 20,
        "warning_threshold": 10,
        "critical_threshold": 5,
        "measurement": "Yanitlar / Gonderimler * 100",
        "frequency": "daily",
    },
    "block_rate": {
        "name": "Block Rate",
        "description": "Block orani (dusuk = iyi)",
        "type": "percentage",
        "target": 0.5,
        "warning_threshold": 2,
        "critical_threshold": 5,
        "measurement": "Blocklar / Gonderimler * 100",
        "frequency": "realtime",
    },
    "report_rate": {
        "name": "Report Rate",
        "description": "Spam report orani (dusuk = iyi)",
        "type": "percentage",
        "target": 0.1,
        "warning_threshold": 1,
        "critical_threshold": 2,
        "measurement": "Reportlar / Gonderimler * 100",
        "frequency": "realtime",
    },
    "fatigue_growth": {
        "name": "Fatigue Score Growth",
        "description": "Fatigue skorunun degisimi (negatif = iyi)",
        "type": "float",
        "target": -0.1,
        "warning_threshold": 0.2,
        "critical_threshold": 0.4,
        "measurement": "Ortalama fatigue skoru degisimi (haftalik)",
        "frequency": "weekly",
    },
    "tenant_trust_score": {
        "name": "Tenant Trust Score",
        "description": "Tenant trust skoru (yuksek = iyi)",
        "type": "float",
        "target": 75,
        "warning_threshold": 60,
        "critical_threshold": 40,
        "measurement": "8-bilesen trust skoru",
        "frequency": "daily",
    },
    "queue_latency": {
        "name": "Queue Latency",
        "description": "Celery queue islem gecikmesi",
        "type": "seconds",
        "target": 5,
        "warning_threshold": 30,
        "critical_threshold": 120,
        "measurement": "Task submission -> execution arasi sure",
        "frequency": "realtime",
    },
    "support_sla": {
        "name": "Support SLA",
        "description": "Support yanit SLA uyumu",
        "type": "percentage",
        "target": 95,
        "warning_threshold": 85,
        "critical_threshold": 70,
        "measurement": "SLA icinde yanitlanan ticket / Toplam ticket",
        "frequency": "daily",
    },
    "webhook_reliability": {
        "name": "Webhook Reliability",
        "description": "Webhook basari orani",
        "type": "percentage",
        "target": 99,
        "warning_threshold": 95,
        "critical_threshold": 90,
        "measurement": "Basarili webhook / Toplam webhook * 100",
        "frequency": "realtime",
    },
    "rollout_health": {
        "name": "Rollout Health Score",
        "description": "Genel rollout saglik skoru",
        "type": "percentage",
        "target": 90,
        "warning_threshold": 70,
        "critical_threshold": 50,
        "measurement": "Tum metriklerin agirlikli ortalamasi",
        "frequency": "daily",
    },
    "ai_cost": {
        "name": "AI Cost (USD)",
        "description": "Gunluk AI maliyeti",
        "type": "usd",
        "target": 5,
        "warning_threshold": 10,
        "critical_threshold": 20,
        "measurement": "Gunluk OpenAI API maliyeti",
        "frequency": "daily",
    },
    "approval_queue_depth": {
        "name": "Approval Queue Depth",
        "description": "Bekleyen onay sayisi",
        "type": "count",
        "target": 10,
        "warning_threshold": 30,
        "critical_threshold": 50,
        "measurement": "Pending approval count",
        "frequency": "realtime",
    },
    "platform_reputation": {
        "name": "Platform Reputation",
        "description": "Platform reputation skoru",
        "type": "float",
        "target": 80,
        "warning_threshold": 60,
        "critical_threshold": 40,
        "measurement": "Base reputation - penalties",
        "frequency": "daily",
    },
}


def generate_sla_dashboard() -> dict:
    """Generate SLA tracking dashboard config."""
    return {
        "sla_targets": {
            "support_response": {"target": "4 saat", "measured": "ticket_response_time"},
            "ai_approval": {"target": "5 dk", "measured": "approval_queue_latency"},
            "api_response": {"target": "200 ms", "measured": "p95_response_time"},
            "webhook_delivery": {"target": "10 sn", "measured": "webhook_latency"},
            "erp_sync": {"target": "5 sn", "measured": "sync_latency"},
            "queue_processing": {"target": "5 sn", "measured": "task_execution_time"},
        },
        "alert_rules": [
            {"metric": "support_response", "threshold": "6 saat", "severity": "warning"},
            {"metric": "support_response", "threshold": "8 saat", "severity": "critical"},
            {"metric": "ai_approval", "threshold": "15 dk", "severity": "warning"},
            {"metric": "ai_approval", "threshold": "30 dk", "severity": "critical"},
            {"metric": "api_response", "threshold": "500 ms", "severity": "warning"},
            {"metric": "api_response", "threshold": "1000 ms", "severity": "critical"},
        ],
    }


def main() -> int:
    print("=" * 70)
    print("  PILOT OPERATIONS TRACKING")
    print("=" * 70)

    print("\n--- Izleme Metrikleri ---")
    for key, metric in OPERATIONS_METRICS.items():
        print(f"\n  {metric['name']} ({key})")
        print(f"    Aciklama: {metric['description']}")
        print(f"    Hedef: {metric['target']}")
        print(f"    Uyari: {metric['warning_threshold']}")
        print(f"    Kritik: {metric['critical_threshold']}")
        print(f"    Frekans: {metric['frequency']}")
        print(f"    Olcum: {metric['measurement']}")

    # SLA Dashboard
    sla = generate_sla_dashboard()
    print(f"\n--- SLA Dashboard ---")
    for metric, config in sla["sla_targets"].items():
        print(f"  {metric}: {config['target']} (olcum: {config['measured']})")

    print(f"\n--- Alert Kurallari ---")
    for rule in sla["alert_rules"]:
        print(f"  {rule['metric']}: {rule['threshold']} ({rule['severity']})")

    # Tracking template
    tracking_template = {
        "tenant_id": "",
        "date": "",
        "metrics": {k: None for k in OPERATIONS_METRICS.keys()},
        "alerts": [],
        "actions_taken": [],
        "notes": "",
    }

    # Save
    output_path = PROJECT_ROOT / "scripts" / "staging" / "operations_tracking.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "metrics": OPERATIONS_METRICS,
            "sla": sla,
            "tracking_template": tracking_template,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2, ensure_ascii=False)

    print(f"\n  Tracking config: {output_path}")
    print(f"  Metrik sayisi: {len(OPERATIONS_METRICS)}")
    print(f"\n  DURUM: Operasyon takip sistemi hazir")
    return 0


if __name__ == "__main__":
    sys.exit(main())
