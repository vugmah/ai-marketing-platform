"""Queue Reliability Test

Validates Celery queue configuration without requiring running workers.
Reads configuration files and checks for reliability patterns.

Usage:
    cd backend && python scripts/staging/queue_reliability_test.py
"""

import ast
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def check_celery_config() -> dict:
    """Find and validate Celery configuration files."""
    results = {
        "config_files": [],
        "broker_url": None,
        "result_backend": None,
        "task_routes": False,
        "beat_schedule": False,
        "retry_policy": False,
        "dlq_configured": False,
    }

    # Search for Celery config
    for pattern in ["celeryconfig.py", "celery_app.py", "celery.py", "tasks.py"]:
        for f in PROJECT_ROOT.rglob(pattern):
            results["config_files"].append(str(f.relative_to(PROJECT_ROOT)))

    # Parse celery_app.py if found
    celery_app = PROJECT_ROOT / "app" / "celery_app.py"
    if celery_app.exists():
        with open(celery_app, "r", encoding="utf-8") as fh:
            content = fh.read()

        results["broker_url"] = "broker_url" in content or "BROKER_URL" in content
        results["result_backend"] = "result_backend" in content or "RESULT_BACKEND" in content
        results["task_routes"] = "task_routes" in content or "queue" in content.lower()
        results["beat_schedule"] = "beat_schedule" in content or "beat" in content.lower()
        results["retry_policy"] = "retry" in content.lower() and "max_retries" in content.lower()
        results["dlq_configured"] = "dead_letter" in content.lower() or "dlq" in content.lower()

    return results


def check_task_files() -> dict:
    """Scan for Celery task definitions."""
    tasks = []
    task_files = list(PROJECT_ROOT.rglob("*task*.py"))

    for f in task_files:
        rel = str(f.relative_to(PROJECT_ROOT))
        try:
            with open(f, "r", encoding="utf-8") as fh:
                content = fh.read()

            has_retry = "retry" in content.lower() and "max_retries" in content.lower()
            has_task_decorator = "@app.task" in content or "@celery.task" in content or "@shared_task" in content

            tasks.append({
                "file": rel,
                "has_retry": has_retry,
                "has_task_decorator": has_task_decorator,
            })
        except:
            pass

    return {
        "task_files": task_files,
        "tasks": tasks,
        "total": len(tasks),
        "with_retry": sum(1 for t in tasks if t["has_retry"]),
        "without_retry": sum(1 for t in tasks if not t["has_retry"]),
    }


def check_redis_connection() -> dict:
    """Check Redis connection string validity."""
    results = {"configured": False, "url": None}

    env_files = [".env.staging", ".env.production", ".env.example", ".env"]
    for env_file in env_files:
        env_path = PROJECT_ROOT.parent / env_file
        if not env_path.exists():
            env_path = PROJECT_ROOT / env_file
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "REDIS" in line or "CELERY_BROKER" in line or "result_backend" in line:
                        results["configured"] = True
                        results["url"] = line.strip()
    return results


def main() -> int:
    print("=" * 60)
    print("QUEUE RELIABILITY TEST")
    print("=" * 60)

    # 1. Celery config
    print("\n--- 1. Celery Configuration ---")
    config = check_celery_config()
    if config["config_files"]:
        print(f"  Found config files: {', '.join(config['config_files'])}")
    else:
        print("  WARNING: No Celery config files found")

    checks = [
        ("Broker URL", config["broker_url"]),
        ("Result Backend", config["result_backend"]),
        ("Task Routes", config["task_routes"]),
        ("Beat Schedule", config["beat_schedule"]),
        ("Retry Policy", config["retry_policy"]),
        ("DLQ Configured", config["dlq_configured"]),
    ]
    for name, ok in checks:
        status = "OK" if ok else "MISSING"
        print(f"  [{status}] {name}")

    # 2. Task files
    print("\n--- 2. Task Definitions ---")
    tasks = check_task_files()
    print(f"  Task files found: {tasks['total']}")
    print(f"  With retry logic: {tasks['with_retry']}")
    print(f"  Without retry: {tasks['without_retry']}")
    for t in tasks["tasks"][:5]:
        retry = "retry" if t["has_retry"] else "no-retry"
        print(f"    - {t['file']} [{retry}]")

    # 3. Redis connection
    print("\n--- 3. Redis Connection ---")
    redis = check_redis_connection()
    if redis["configured"]:
        print(f"  OK: Redis connection configured")
        if redis["url"]:
            print(f"  Config: {redis['url']}")
    else:
        print(f"  WARNING: No Redis connection string found")

    # Summary
    score = sum(1 for _, ok in checks if ok)
    total = len(checks)
    print(f"\n{'=' * 60}")
    print(f"Config checks: {score}/{total}")
    print(f"Task files: {tasks['total']}")
    print(f"Tasks with retry: {tasks['with_retry']}")

    if score >= 4 and tasks["with_retry"] == tasks["total"] and tasks["total"] > 0:
        print("STATUS: QUEUE RELIABILITY - GOOD")
        return 0
    elif score >= 3:
        print("STATUS: QUEUE RELIABILITY - ACCEPTABLE with gaps")
        return 0
    else:
        print("STATUS: QUEUE RELIABILITY - REVIEW REQUIRED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
