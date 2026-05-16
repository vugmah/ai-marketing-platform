"""Staging Deployment Orchestrator

Staging ortamini ayaga kaldirir:
- MySQL 8
- Redis
- Celery worker + beat
- FastAPI backend
- Nginx reverse proxy
- Prometheus
- Grafana
- MinIO

Usage: cd backend && python scripts/staging/deploy_staging.py
"""

import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Staging services and their health endpoints
SERVICES = [
    ("mysql", "MySQL 8.0", 30),
    ("redis", "Redis 7", 10),
    ("minio", "MinIO Object Storage", 15),
    ("backend", "FastAPI Backend", 30),
    ("celery_worker", "Celery Worker", 30),
    ("celery_beat", "Celery Beat", 15),
    ("nginx", "Nginx Reverse Proxy", 10),
    ("prometheus", "Prometheus", 10),
    ("grafana", "Grafana", 15),
]

HEALTH_CHECKS = [
    ("Backend /api/v2/health/", "http://localhost:8001/api/v2/health/"),
    ("Backend /api/v2/health/ready", "http://localhost:8001/api/v2/health/ready"),
    ("Backend /api/v2/health/live", "http://localhost:8001/api/v2/health/live"),
    ("Backend /api/v2/health/db", "http://localhost:8001/api/v2/health/db"),
    ("Backend /api/v2/health/redis", "http://localhost:8001/api/v2/health/redis"),
    ("Prometheus", "http://localhost:9091/-/healthy"),
    ("Grafana", "http://localhost:3001/api/health"),
]


def run_command(cmd: list[str], cwd: Path = None, timeout: int = 60) -> tuple[int, str, str]:
    """Run a shell command and return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)


def check_docker() -> bool:
    """Check if Docker is available."""
    code, _, _ = run_command(["docker", "info"])
    if code != 0:
        print("  [ERROR] Docker is not running or not installed")
        return False

    code, _, _ = run_command(["docker-compose", "version"])
    if code != 0:
        # Try docker compose (v2)
        code, _, _ = run_command(["docker", "compose", "version"])
        if code != 0:
            print("  [ERROR] docker-compose not found")
            return False

    print("  [OK] Docker available")
    return True


def check_env_file() -> bool:
    """Check .env.staging exists."""
    env_file = PROJECT_ROOT / ".." / ".env.staging"
    if not env_file.exists():
        print(f"  [WARN] .env.staging not found at {env_file}")
        return False
    print(f"  [OK] .env.staging found")
    return True


def deploy_infra() -> bool:
    """Deploy staging infrastructure with docker-compose."""
    print("\n--- Staging Infrastructure Deployment ---")

    compose_file = PROJECT_ROOT / ".." / "docker-compose.staging.yml"
    if not compose_file.exists():
        print(f"  [ERROR] docker-compose.staging.yml not found")
        return False

    # Pull images
    print("\n  [STEP] Pulling Docker images...")
    code, out, err = run_command(
        ["docker-compose", "-f", str(compose_file), "pull"],
        cwd=PROJECT_ROOT / "..",
        timeout=120,
    )
    if code != 0:
        print(f"  [WARN] Pull failed (will use local images): {err[:200]}")
    else:
        print("  [OK] Images pulled")

    # Start services
    print("\n  [STEP] Starting services...")
    code, out, err = run_command(
        ["docker-compose", "-f", str(compose_file), "up", "-d", "--build"],
        cwd=PROJECT_ROOT / "..",
        timeout=300,
    )
    if code != 0:
        print(f"  [ERROR] Failed to start services: {err[:500]}")
        return False

    print("  [OK] Services started")
    return True


def wait_for_services() -> dict[str, bool]:
    """Wait for all services to be healthy."""
    print("\n--- Waiting for Services ---")

    compose_file = PROJECT_ROOT / ".." / "docker-compose.staging.yml"
    results = {}

    for service_name, display_name, max_wait in SERVICES:
        print(f"\n  [WAIT] {display_name} (max {max_wait}s)...")
        healthy = False

        for i in range(max_wait):
            code, out, _ = run_command(
                ["docker-compose", "-f", str(compose_file), "ps", service_name],
                cwd=PROJECT_ROOT / "..",
            )
            if "healthy" in out.lower() or "Up" in out:
                healthy = True
                print(f"  [OK] {display_name} ready ({i+1}s)")
                break
            time.sleep(1)

        if not healthy:
            print(f"  [WARN] {display_name} not healthy after {max_wait}s")

        results[service_name] = healthy

    return results


def run_health_checks() -> dict[str, bool]:
    """Run health checks against running services."""
    print("\n--- Health Checks ---")

    results = {}
    for name, url in HEALTH_CHECKS:
        try:
            import urllib.request
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "AIMP-Deploy-Check/1.0")

            try:
                resp = urllib.request.urlopen(req, timeout=10)
                status = resp.getcode()
                if status in (200, 202):
                    print(f"  [OK] {name}: HTTP {status}")
                    results[name] = True
                else:
                    print(f"  [WARN] {name}: HTTP {status}")
                    results[name] = False
            except urllib.error.HTTPError as e:
                if e.code == 503:
                    print(f"  [WARN] {name}: HTTP 503 (service starting)")
                    results[name] = False
                else:
                    print(f"  [FAIL] {name}: HTTP {e.code}")
                    results[name] = False
            except Exception as e:
                print(f"  [FAIL] {name}: {str(e)[:100]}")
                results[name] = False

        except ImportError:
            # Fallback to curl
            code, _, _ = run_command(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url])
            if code == 0:
                print(f"  [OK] {name}: reachable")
                results[name] = True
            else:
                print(f"  [FAIL] {name}: unreachable")
                results[name] = False

    return results


def check_openapi() -> bool:
    """Check OpenAPI schema is accessible."""
    print("\n--- OpenAPI Schema ---")

    url = "http://localhost:8001/api/openapi.json"
    try:
        import urllib.request
        import json

        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))

        title = data.get("info", {}).get("title", "unknown")
        version = data.get("info", {}).get("version", "unknown")
        paths = len(data.get("paths", {}))

        print(f"  [OK] OpenAPI: {title} v{version}")
        print(f"  [OK] Endpoints: {paths} paths")

        # Check for follower endpoints
        follower_paths = [p for p in data.get("paths", {}) if "/followers" in p]
        print(f"  [OK] Follower endpoints: {len(follower_paths)}")

        return True
    except Exception as e:
        print(f"  [FAIL] OpenAPI check failed: {e}")
        return False


def check_migration_status() -> bool:
    """Check database migration status."""
    print("\n--- Migration Status ---")

    # Run alembic current
    code, out, err = run_command(
        ["docker-compose", "-f", "../docker-compose.staging.yml", "exec", "-T", "backend",
         "alembic", "current"],
        cwd=PROJECT_ROOT,
        timeout=30,
    )

    if code != 0:
        print(f"  [WARN] Could not check migration status: {err[:200]}")
        return False

    if "head" in out.lower():
        print(f"  [OK] Database at latest migration")
    else:
        print(f"  [INFO] Migration status: {out.strip()[:100]}")

    return True


def generate_report(service_status: dict, health_status: dict) -> dict:
    """Generate deployment report."""
    total_services = len(service_status)
    healthy_services = sum(1 for v in service_status.values() if v)

    total_checks = len(health_status)
    passed_checks = sum(1 for v in health_status.values() if v)

    return {
        "deployment_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "services": {
            "total": total_services,
            "healthy": healthy_services,
            "unhealthy": total_services - healthy_services,
            "details": service_status,
        },
        "health_checks": {
            "total": total_checks,
            "passed": passed_checks,
            "failed": total_checks - passed_checks,
            "details": health_status,
        },
        "status": "healthy" if healthy_services == total_services else "degraded",
    }


def main() -> int:
    print("=" * 70)
    print("  STAGING DEPLOYMENT ORCHESTRATOR")
    print("  Target: AI Marketing Platform v2.0")
    print("=" * 70)

    # Step 1: Prerequisites
    print("\n--- Prerequisites ---")
    if not check_docker():
        return 1
    check_env_file()

    # Step 2: Deploy infrastructure
    if not deploy_infra():
        return 1

    # Step 3: Wait for services
    service_status = wait_for_services()

    # Step 4: Health checks
    health_status = run_health_checks()

    # Step 5: OpenAPI check
    check_openapi()

    # Step 6: Migration status
    check_migration_status()

    # Step 7: Generate report
    report = generate_report(service_status, health_status)

    # Save report
    report_path = PROJECT_ROOT / "scripts" / "staging" / "deploy_report.json"
    import json
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  DEPLOYMENT REPORT")
    print(f"{'=' * 70}")
    print(f"  Services: {report['services']['healthy']}/{report['services']['total']} healthy")
    print(f"  Health checks: {report['health_checks']['passed']}/{report['health_checks']['total']} passed")
    print(f"  Status: {report['status'].upper()}")
    print(f"  Report: {report_path}")

    if report["services"]["unhealthy"] == 0:
        print(f"\n  STATUS: STAGING DEPLOYMENT SUCCESSFUL")
        return 0
    elif report["services"]["unhealthy"] <= 2:
        print(f"\n  STATUS: DEPLOYED WITH {report['services']['unhealthy']} WARNING(S)")
        return 0
    else:
        print(f"\n  STATUS: DEPLOYMENT DEGRADED - {report['services']['unhealthy']} services unhealthy")
        return 1


if __name__ == "__main__":
    sys.exit(main())
