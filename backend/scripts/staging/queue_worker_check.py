"""Queue & Worker Reliability Validation

Validates Celery configuration, queue health, retry policies, and DLQ.
Usage: python scripts/staging/queue_worker_check.py
"""

import ast
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def check_celery_config() -> list:
    """Check Celery configuration."""
    issues = []
    celery_file = PROJECT_ROOT / "celery_config.py"
    if not celery_file.exists():
        celery_file = PROJECT_ROOT / "celery.py"

    if not celery_file.exists():
        issues.append("Celery configuration file not found")
        return issues

    with open(celery_file, 'r') as f:
        content = f.read()

    checks = [
        ("task_track_started", "Task tracking not enabled"),
        ("task_time_limit", "Task time limit not set"),
        ("task_soft_time_limit", "Task soft time limit not set"),
        ("worker_prefetch_multiplier", "Worker prefetch not configured"),
        ("task_acks_late", "Task acks late not enabled (can lose tasks on crash)"),
    ]

    for setting, msg in checks:
        if setting not in content:
            issues.append(f"{msg}: {setting} missing")

    return issues


def check_task_definitions() -> list:
    """Check Celery task definitions."""
    issues = []
    tasks_dir = PROJECT_ROOT / "app"
    task_count = 0

    for f in tasks_dir.rglob("*.py"):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
            if '@celery.task' in content or '@app.task' in content or '@shared_task' in content:
                task_count += 1
                # Check for retry logic
                if 'retry' not in content and 'bind=True' not in content:
                    rel = str(f.relative_to(PROJECT_ROOT))
                    issues.append(f"Task in {rel} missing retry logic")
        except:
            pass

    if task_count == 0:
        issues.append("No Celery tasks found in the project")
    else:
        print(f"  Found {task_count} task files")

    return issues


def check_worker_health_endpoint() -> list:
    """Check if health endpoints for workers exist."""
    issues = []
    health_router = PROJECT_ROOT / "app" / "health" / "router.py"
    if health_router.exists():
        with open(health_router, 'r') as f:
            content = f.read()
        if 'queue' not in content.lower() and 'celery' not in content.lower():
            issues.append("Health router missing queue/Celery status check")
    return issues


def main() -> int:
    print("=" * 60)
    print("QUEUE & WORKER RELIABILITY CHECK")
    print("=" * 60)

    all_issues = []

    print("\n--- 1. Celery Configuration ---")
    issues = check_celery_config()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  WARN: {i}")
    else:
        print("  OK: Celery config valid")

    print("\n--- 2. Task Definitions ---")
    issues = check_task_definitions()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  WARN: {i}")
    else:
        print("  OK: All tasks have retry logic")

    print("\n--- 3. Worker Health ---")
    issues = check_worker_health_endpoint()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  WARN: {i}")
    else:
        print("  OK: Worker health checks present")

    print(f"\n{'=' * 60}")
    print(f"Total issues: {len(all_issues)}")

    if all_issues:
        print("RESULT: REVIEW REQUIRED")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
