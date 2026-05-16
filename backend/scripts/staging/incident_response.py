"""Incident Response & Rollback Procedures

Incident response prosedurleri ve rollback hazirliklari.

Kapsar:
- Rollback prosedurleri
- DB restore
- Redis recovery
- Queue replay
- AI disable switch
- Tenant emergency disable
- Feature flag rollback
- Incident escalation chain

Usage: cd backend && python scripts/staging/incident_response.py [command]
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


INCIDENT_RESPONSE_PLAN = {
    "version": "1.0",
    "created_at": "2026-05-16",
    "escalation_chain": [
        {
            "level": "L1 - On-Call Engineer",
            "response_time_minutes": 15,
            "responsibilities": [
                "Incident tespiti ve klasifikasyonu",
                "Ilk mudahale (restart, failover)",
                "L2'ye escalation karari",
                "Incident kanalinda bildirim",
            ],
            "contact": "l1-oncall@aimp.internal",
        },
        {
            "level": "L2 - Tech Lead",
            "response_time_minutes": 30,
            "responsibilities": [
                "Teknik analiz ve root cause",
                "Rollback karari",
                "L3'e escalation (P1 icin)",
                "Musteri iletisimi (P1/P2)",
            ],
            "contact": "l2-tech@aimp.internal",
        },
        {
            "level": "L3 - Engineering Manager",
            "response_time_minutes": 60,
            "responsibilities": [
                "Stratejik kararlar",
                "Musteri yonetimi",
                "Post-mortem organizasyonu",
                "Proses iyilestirme",
            ],
            "contact": "l3-eng@aimp.internal",
        },
    ],

    "severity_levels": {
        "P1": {
            "name": "Critical",
            "description": "Servis tamamen kullanilamaz, veri kaybi riski",
            "response_time_minutes": 15,
            "escalation_time_minutes": 30,
            "channels": ["pilot-ops-critical", "phone-l1", "phone-l2"],
            "auto_actions": [
                "Tum pilot tenantlar temporary disable",
                "AI auto-send KAPAT (zaten kapali)",
                "Webhook processing DURDUR",
                "Incident kanalinda otomatik alarm",
            ],
        },
        "P2": {
            "name": "High",
            "description": "Onemli fonksiyonlar etkilenmis, workaround var",
            "response_time_minutes": 30,
            "escalation_time_minutes": 60,
            "channels": ["pilot-ops"],
            "auto_actions": [
                "Etkilenen tenantlari disable",
                "AI processing throttle",
            ],
        },
        "P3": {
            "name": "Medium",
            "description": "Kismi etki, is surekligi devam ediyor",
            "response_time_minutes": 120,
            "escalation_time_minutes": 240,
            "channels": ["pilot-ops"],
            "auto_actions": [
                "Monitoring alert olustur",
                "Log aggregation baslat",
            ],
        },
        "P4": {
            "name": "Low",
            "description": "Kozmetik/minor issue",
            "response_time_minutes": 480,
            "escalation_time_minutes": 9999,
            "channels": ["pilot-ops"],
            "auto_actions": [
                "Jira ticket olustur",
            ],
        },
    },

    "rollback_procedures": {
        "full_rollback": {
            "description": "Tum staging ortamini onceki surume rollback",
            "steps": [
                "1. docker-compose -f docker-compose.staging.yml down",
                "2. DB backup'dan restore: ./scripts/restore-db.sh [backup_file]",
                "3. Redis flush: docker exec aimp_staging_redis redis-cli FLUSHDB",
                "4. Onceki Docker image'a don: docker tag aimp-backend:previous aimp-backend:latest",
                "5. docker-compose -f docker-compose.staging.yml up -d",
                "6. Health check bekle: ./scripts/health-check.sh http://localhost:8001",
                "7. Pilot tenantlari yeniden enable et",
            ],
            "estimated_time_minutes": 15,
            "risk": "low",
        },
        "partial_rollback": {
            "description": "Sadece etkilenen servisi rollback",
            "steps": [
                "1. Etkilenen servisi tespit et",
                "2. docker-compose -f docker-compose.staging.yml stop [service]",
                "3. Onceki image'a don",
                "4. docker-compose -f docker-compose.staging.yml up -d [service]",
                "5. Health check",
            ],
            "estimated_time_minutes": 5,
            "risk": "low",
        },
        "db_rollback": {
            "description": "Alembic downgrade ile DB rollback",
            "steps": [
                "1. Mevcut migration'u kontrol et: alembic current",
                "2. Hedef migration'a downgrade: alembic downgrade [revision]",
                "3. Tablo durumunu dogrula",
                "4. Application'u yeniden baslat",
            ],
            "estimated_time_minutes": 10,
            "risk": "medium",
        },
    },

    "recovery_procedures": {
        "redis_failure": {
            "description": "Redis failure senaryosu",
            "steps": [
                "1. Redis container durumunu kontrol et: docker ps | grep redis",
                "2. Redis loglarini kontrol et: docker logs aimp_staging_redis",
                "3. Redis restart: docker-compose -f docker-compose.staging.yml restart redis",
                "4. Memory kullanimini kontrol et: redis-cli INFO memory",
                "5. Eger persistent data bozuksa: Redis data volumunu temizle ve yeniden baslat",
                "6. Celery worker'lari restart et (queue state kaybi olabilir)",
                "7. Queue'yu kontrol et: celery -A app.celery_app inspect active",
            ],
            "estimated_time_minutes": 5,
        },
        "queue_failure": {
            "description": "Celery queue failure senaryosu",
            "steps": [
                "1. Celery worker durumunu kontrol et: docker ps | grep celery",
                "2. Worker loglarini kontrol et: docker logs aimp_staging_celery",
                "3. Celery inspect: celery -A app.celery_app inspect ping",
                "4. Worker'lari restart et: docker-compose restart celery_worker",
                "5. Beat'i restart et: docker-compose restart celery_beat",
                "6. DLQ (dead letter queue) kontrol et",
                "7. Failed task'lari replay et: celery -A app.celery_app control revoke [task_id]",
            ],
            "estimated_time_minutes": 10,
        },
        "webhook_outage": {
            "description": "Webhook endpoint outage senaryosu",
            "steps": [
                "1. Webhook endpoint'ini kontrol et: curl -I [webhook_url]",
                "2. Webhook loglarini kontrol et",
                "3. Retry queue'yu kontrol et",
                "4. Eger external servis down: retry mekanizmasini bekle",
                "5. Webhook'lari yeniden gonder: queue'ya replay et",
                "6. Fallback mekanizmasini aktif et (varsa)",
            ],
            "estimated_time_minutes": 15,
        },
        "ai_outage": {
            "description": "AI service outage senaryosu",
            "steps": [
                "1. AI service durumunu kontrol et",
                "2. OpenAI API status kontrol et",
                "3. Fallback mode'a gec (template-based yanıtlar)",
                "4. AI_SUPERVISED_MODE=True kontrol et",
                "5. AI request'leri throttle et",
                "6. Operator'lara bildirim gonder",
                "7. Cost limit kontrol et (quota exceeded olabilir)",
            ],
            "estimated_time_minutes": 5,
        },
    },

    "emergency_switches": {
        "ai_disable": {
            "command": "docker-compose -f docker-compose.staging.yml exec backend python -c \"import os; os.environ['AI_SUPERVISED_MODE']='true'; os.environ['ENABLE_AI_SAFETY']='true'\"",
            "description": "Tum AI islemlerini supervised mode'a al",
            "effect": "AI yanıtlari onay gerektirir",
        },
        "tenant_disable": {
            "command": "PUT /api/v2/admin/tenants/{tenant_id}/status {\"status\": \"disabled\"}",
            "description": "Belirli bir tenant'i devre disi birak",
            "effect": "Tenant API erisimi engellenir",
        },
        "all_tenants_disable": {
            "command": "docker-compose -f docker-compose.staging.yml exec backend python -c \"tenant_ids=['pilot_001','pilot_002','pilot_003']; ...\"",
            "description": "Tum pilot tenantlari devre disi birak",
            "effect": "Tum pilot erisimi engellenir",
        },
        "feature_flag_rollback": {
            "command": "PATCH /api/v2/admin/feature-flags {\"feature\": \"name\", \"enabled\": false}",
            "description": "Belirli bir feature flag'i kapat",
            "effect": "Feature devre disi kalir",
        },
        "webhook_disable": {
            "command": "docker-compose -f docker-compose.staging.yml exec backend python -c \"os.environ['WEBHOOK_PROCESSING_ENABLED']='false'\"",
            "description": "Webhook islemlerini durdur",
            "effect": "Yeni webhook'lar islenmez",
        },
    },
}


def print_rollout_abort_criteria():
    """Print rollout abort criteria."""
    print("\n--- Pilot Rollout Abort Kriterleri ---")
    criteria = [
        (">3 P1 incident/hafta", "Servis kararsizligi"),
        ("Veri kaybi", "DB corruption veya migration hatasi"),
        ("Queue bozulmasi", "Task loss veya DLK dolmasi"),
        ("AI safety violation", "Onay disi mesaj gonderimi"),
        ("Redis saturation", "Memory %95+ surekli"),
        ("Webhook failure spike", "%50+ webhook basarisiz"),
        ("Spam-risk escalation", "Tenant spam skoru >0.7"),
        ("Platform reputation dususu", "Herhangi bir platform <40"),
        ("Operator override >80%", "AI sistem guvenilmez"),
    ]
    for criterion, desc in criteria:
        print(f"  [ABORT] {criterion}: {desc}")


def main() -> int:
    print("=" * 70)
    print("  INCIDENT RESPONSE & ROLLBACK READINESS")
    print("=" * 70)

    # Print escalation chain
    print("\n--- Escalation Chain ---")
    for level in INCIDENT_RESPONSE_PLAN["escalation_chain"]:
        print(f"\n  {level['level']}")
        print(f"    Yanit suresi: {level['response_time_minutes']} dk")
        print(f"    Iletisim: {level['contact']}")
        for resp in level['responsibilities']:
            print(f"    - {resp}")

    # Print severity levels
    print("\n--- Severity Levels ---")
    for severity, details in INCIDENT_RESPONSE_PLAN["severity_levels"].items():
        print(f"\n  {severity} - {details['name']}")
        print(f"    Yanit: {details['response_time_minutes']} dk")
        print(f"    Kanallar: {', '.join(details['channels'])}")
        print(f"    Otomatik aksiyonlar:")
        for action in details['auto_actions']:
            print(f"      - {action}")

    # Print rollback procedures
    print("\n--- Rollback Prosedurleri ---")
    for name, proc in INCIDENT_RESPONSE_PLAN["rollback_procedures"].items():
        print(f"\n  {name.upper()}: {proc['description']}")
        print(f"    Tahmini sure: {proc['estimated_time_minutes']} dk")
        print(f"    Risk: {proc['risk']}")
        for step in proc['steps']:
            print(f"    {step}")

    # Print recovery procedures
    print("\n--- Recovery Prosedurleri ---")
    for name, proc in INCIDENT_RESPONSE_PLAN["recovery_procedures"].items():
        print(f"\n  {name.upper()}: {proc['description']}")
        print(f"    Tahmini sure: {proc['estimated_time_minutes']} dk")
        for step in proc['steps']:
            print(f"    {step}")

    # Print emergency switches
    print("\n--- Emergency Switches ---")
    for name, switch in INCIDENT_RESPONSE_PLAN["emergency_switches"].items():
        print(f"\n  {name.upper()}")
        print(f"    Komut: {switch['command']}")
        print(f"    Aciklama: {switch['description']}")
        print(f"    Etki: {switch['effect']}")

    # Print abort criteria
    print_rollout_abort_criteria()

    # Save incident response plan
    output_path = PROJECT_ROOT / "scripts" / "staging" / "incident_response_plan.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(INCIDENT_RESPONSE_PLAN, f, indent=2, ensure_ascii=False)

    print(f"\n  Plan kaydedildi: {output_path}")
    print(f"\n  DURUM: Incident response plani hazir")
    return 0


if __name__ == "__main__":
    sys.exit(main())
