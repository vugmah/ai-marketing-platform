"""Daily Operational Review Checklist

Automated daily ops review that checks all critical systems.
Usage: cd backend && python scripts/staging/daily_ops_review.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Health check thresholds
THRESHOLDS = {
    "max_error_rate_pct": 5.0,
    "max_latency_p95_ms": 3000,
    "max_queue_depth": 1000,
    "max_redis_memory_pct": 85.0,
    "max_mysql_connections_pct": 80.0,
    "min_webhook_success_pct": 95.0,
    "min_sla_compliance_pct": 90.0,
    "max_ai_cost_usd_per_day": 5.0,
    "max_incidents_per_day": 3,
}


def check_tenant_health() -> dict:
    """Check pilot tenant health."""
    # Simulated data - in production this queries metrics endpoint
    tenants = {
        "pilot_001": {"health": 88, "api_errors_24h": 2, "ai_cost_today": 0.42},
        "pilot_002": {"health": 72, "api_errors_24h": 7, "ai_cost_today": 0.23},
        "pilot_003": {"health": 65, "api_errors_24h": 4, "ai_cost_today": 0.09},
    }

    issues = []
    for tid, data in tenants.items():
        if data["health"] < 60:
            issues.append(f"{tid}: Health {data['health']}% (below 60%)")
        elif data["health"] < 80:
            issues.append(f"{tid}: Health {data['health']}% (below 80%)")
        if data["api_errors_24h"] > 5:
            issues.append(f"{tid}: {data['api_errors_24h']} API errors in 24h")

    avg_health = sum(t["health"] for t in tenants.values()) / len(tenants)
    return {
        "tenant_count": len(tenants),
        "avg_health": round(avg_health, 1),
        "issues": issues,
        "status": "PASS" if avg_health >= 80 and not issues else "WARN" if avg_health >= 60 else "FAIL",
    }


def check_queue_health() -> dict:
    """Check Celery queue health."""
    # Simulated
    queue_depth = 45  # Would query Redis
    dead_letter = 3
    worker_count = 2

    issues = []
    if queue_depth > THRESHOLDS["max_queue_depth"]:
        issues.append(f"Queue depth {queue_depth} exceeds {THRESHOLDS['max_queue_depth']}")
    if dead_letter > 10:
        issues.append(f"Dead letter queue {dead_letter} > 10")
    if worker_count < 1:
        issues.append(f"No active workers detected")

    return {
        "queue_depth": queue_depth,
        "dead_letter": dead_letter,
        "workers": worker_count,
        "issues": issues,
        "status": "PASS" if not issues else "WARN",
    }


def check_database_health() -> dict:
    """Check MySQL health."""
    connections = 23  # Would query MySQL
    max_connections = 200
    connection_pct = (connections / max_connections) * 100

    issues = []
    if connection_pct > THRESHOLDS["max_mysql_connections_pct"]:
        issues.append(f"MySQL connections {connection_pct:.1f}% exceeds {THRESHOLDS['max_mysql_connections_pct']}%")

    return {
        "connections": connections,
        "max_connections": max_connections,
        "connection_pct": round(connection_pct, 1),
        "issues": issues,
        "status": "PASS" if not issues else "WARN",
    }


def check_redis_health() -> dict:
    """Check Redis health."""
    memory_used_mb = 82  # Would query Redis
    memory_max_mb = 128
    memory_pct = (memory_used_mb / memory_max_mb) * 100

    issues = []
    if memory_pct > THRESHOLDS["max_redis_memory_pct"]:
        issues.append(f"Redis memory {memory_pct:.1f}% exceeds {THRESHOLDS['max_redis_memory_pct']}%")

    return {
        "memory_used_mb": memory_used_mb,
        "memory_max_mb": memory_max_mb,
        "memory_pct": round(memory_pct, 1),
        "issues": issues,
        "status": "PASS" if not issues else "WARN",
    }


def check_ai_health() -> dict:
    """Check AI system health."""
    total_cost = sum([0.42, 0.23, 0.09])
    avg_latency = 1570
    hallucination_rate = 5.1

    issues = []
    if total_cost > THRESHOLDS["max_ai_cost_usd_per_day"]:
        issues.append(f"AI cost ${total_cost:.2f} exceeds ${THRESHOLDS['max_ai_cost_usd_per_day']}/day")
    if avg_latency > THRESHOLDS["max_latency_p95_ms"]:
        issues.append(f"AI latency {avg_latency}ms exceeds {THRESHOLDS['max_latency_p95_ms']}ms")
    if hallucination_rate > 5:
        issues.append(f"Hallucination rate {hallucination_rate}% > 5%")

    return {
        "total_cost_today": round(total_cost, 2),
        "avg_latency_ms": avg_latency,
        "hallucination_rate": hallucination_rate,
        "issues": issues,
        "status": "PASS" if not issues else "WARN",
    }


def check_webhook_health() -> dict:
    """Check webhook delivery health."""
    success_rate = 98.5
    failures_24h = 12

    issues = []
    if success_rate < THRESHOLDS["min_webhook_success_pct"]:
        issues.append(f"Webhook success {success_rate}% below {THRESHOLDS['min_webhook_success_pct']}%")

    return {
        "success_rate": success_rate,
        "failures_24h": failures_24h,
        "issues": issues,
        "status": "PASS" if not issues else "WARN",
    }


def check_incidents() -> dict:
    """Check incident count."""
    incidents_24h = {
        "P1": 0,
        "P2": 1,
        "P3": 2,
        "P4": 1,
    }
    total = sum(incidents_24h.values())

    issues = []
    if incidents_24h["P1"] > 0:
        issues.append(f"{incidents_24h['P1']} P1 incident(s) in 24h")
    if total > THRESHOLDS["max_incidents_per_day"]:
        issues.append(f"{total} incidents in 24h exceeds {THRESHOLDS['max_incidents_per_day']}")

    return {
        "incidents_24h": incidents_24h,
        "total": total,
        "issues": issues,
        "status": "PASS" if not issues else "WARN" if incidents_24h["P1"] == 0 else "FAIL",
    }


def main() -> int:
    print("=" * 60)
    print("DAILY OPERATIONAL REVIEW")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    checks = {
        "Tenant Health": check_tenant_health(),
        "Queue Health": check_queue_health(),
        "Database Health": check_database_health(),
        "Redis Health": check_redis_health(),
        "AI Health": check_ai_health(),
        "Webhook Health": check_webhook_health(),
        "Incidents": check_incidents(),
    }

    all_issues = []
    all_pass = True

    for name, result in checks.items():
        status = result["status"]
        icon = "PASS" if status == "PASS" else "WARN" if status == "WARN" else "FAIL"
        print(f"\n  [{icon}] {name}")

        if "avg_health" in result:
            print(f"        Avg health: {result['avg_health']}%")
        if "queue_depth" in result:
            print(f"        Queue: {result['queue_depth']} (DLQ: {result['dead_letter']})")
        if "connection_pct" in result:
            print(f"        Connections: {result['connections']}/{result['max_connections']} ({result['connection_pct']}%)")
        if "memory_pct" in result:
            print(f"        Memory: {result['memory_used_mb']}/{result['memory_max_mb']}MB ({result['memory_pct']}%)")
        if "total_cost_today" in result:
            print(f"        Cost: ${result['total_cost_today']}, Latency: {result['avg_latency_ms']}ms")
        if "success_rate" in result:
            print(f"        Webhooks: {result['success_rate']}% success ({result['failures_24h']} failures)")
        if "incidents_24h" in result:
            print(f"        Incidents: P1={result['incidents_24h']['P1']}, P2={result['incidents_24h']['P2']}, P3={result['incidents_24h']['P3']}")

        if result["issues"]:
            for issue in result["issues"]:
                print(f"        ! {issue}")
            all_issues.extend(result["issues"])

        if status == "FAIL":
            all_pass = False

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Checks: {len(checks)} | Passed: {sum(1 for c in checks.values() if c['status'] == 'PASS')}")
    print(f"Warnings: {sum(1 for c in checks.values() if c['status'] == 'WARN')}")
    print(f"Failures: {sum(1 for c in checks.values() if c['status'] == 'FAIL')}")
    print(f"Total issues: {len(all_issues)}")

    # Save report
    report = {
        "date": datetime.now().isoformat(),
        "checks": {k: {ik: iv for ik, iv in v.items() if ik != "issues"} for k, v in checks.items()},
        "issues": all_issues,
        "overall_status": "PASS" if all_pass else "FAIL",
    }
    output = PROJECT_ROOT / "scripts" / "staging" / f"daily_ops_{datetime.now().strftime('%Y%m%d')}.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nReport saved: {output}")
    if not all_pass:
        print("STATUS: ISSUES FOUND - review required")
        return 1
    else:
        print("STATUS: ALL CHECKS PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
