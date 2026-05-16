"""Staging Health Check Script

Validates all staging services are up and healthy.
Usage: python scripts/staging_health_check.py [--host http://localhost:8001]

Exit codes:
    0 - All services healthy
    1 - One or more services unhealthy
"""

import argparse
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError


def check_url(name: str, url: str, timeout: int = 10) -> dict:
    """Check a single URL and return status."""
    start = time.time()
    try:
        req = Request(url, method="GET")
        req.add_header("User-Agent", "aimp-health-check/2.0")
        with urlopen(req, timeout=timeout) as resp:
            latency = (time.time() - start) * 1000
            body = resp.read(1024).decode("utf-8", errors="ignore")
            return {
                "name": name,
                "url": url,
                "status": resp.status,
                "latency_ms": round(latency, 1),
                "healthy": resp.status < 400,
                "body_preview": body[:100],
            }
    except HTTPError as e:
        return {"name": name, "url": url, "status": e.code, "latency_ms": -1, "healthy": False, "error": str(e)}
    except URLError as e:
        return {"name": name, "url": url, "status": 0, "latency_ms": -1, "healthy": False, "error": str(e.reason)}
    except Exception as e:
        return {"name": name, "url": url, "status": 0, "latency_ms": -1, "healthy": False, "error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="AIMP Staging Health Check")
    parser.add_argument("--host", default="http://localhost:8001", help="Backend host URL")
    parser.add_argument("--redis-host", default="localhost", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=6380, help="Redis port")
    parser.add_argument("--mysql-host", default="localhost", help="MySQL host")
    parser.add_argument("--mysql-port", type=int, default=3307, help="MySQL port")
    args = parser.parse_args()

    print("=" * 60)
    print("AIMP STAGING HEALTH CHECK")
    print(f"Target: {args.host}")
    print("=" * 60)

    checks = [
        ("Backend API Root", f"{args.host}/api/v2/health"),
        ("Database Health", f"{args.host}/api/v2/health/db"),
        ("Redis Health", f"{args.host}/api/v2/health/redis"),
        ("Queue Health", f"{args.host}/api/v2/health/queue"),
        ("MinIO Health", f"{args.host}/api/v2/health/storage"),
        ("API Docs", f"{args.host}/docs"),
    ]

    results = []
    all_healthy = True

    for name, url in checks:
        result = check_url(name, url)
        results.append(result)
        status = "PASS" if result["healthy"] else "FAIL"
        lat = f"{result['latency_ms']}ms" if result['latency_ms'] >= 0 else "N/A"
        print(f"  [{status}] {name:20s} - HTTP {result['status']} ({lat})")
        if not result["healthy"]:
            all_healthy = False
            if "error" in result:
                print(f"        Error: {result['error']}")

    # Summary
    passed = sum(1 for r in results if r["healthy"])
    total = len(results)

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} checks passed")

    if all_healthy:
        print("STATUS: ALL SERVICES HEALTHY")
        return 0
    else:
        print(f"STATUS: {total - passed} SERVICE(S) UNHEALTHY")
        return 1


if __name__ == "__main__":
    sys.exit(main())
