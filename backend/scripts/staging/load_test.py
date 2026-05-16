"""Load & Stress Testing Script

Simulates concurrent users hitting the staging API.
Usage: python scripts/staging/load_test.py --host http://localhost:8001 --users 20 --duration 60
"""
import argparse
import asyncio
import random
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def make_request(url: str, timeout: int = 10) -> dict:
    start = time.time()
    try:
        req = Request(url, method="GET")
        req.add_header("User-Agent", "aimp-load-test/1.0")
        with urlopen(req, timeout=timeout) as resp:
            return {
                "ok": True, "status": resp.status,
                "latency_ms": round((time.time() - start) * 1000, 1),
            }
    except HTTPError as e:
        return {"ok": False, "status": e.code, "latency_ms": -1}
    except Exception as e:
        return {"ok": False, "status": 0, "latency_ms": -1, "error": str(e)[:50]}


ENDPOINTS = [
    "/api/v2/health",
    "/api/v2/health/db",
    "/api/v2/health/redis",
    "/docs",
]


def worker(host: str, worker_id: int, duration: int, results: list):
    """Single worker simulating a user."""
    end_time = time.time() + duration
    count = 0
    while time.time() < end_time:
        endpoint = random.choice(ENDPOINTS)
        result = make_request(f"{host}{endpoint}")
        result["worker"] = worker_id
        result["endpoint"] = endpoint
        results.append(result)
        count += 1
        time.sleep(random.uniform(0.1, 1.0))  # Think time
    return count


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://localhost:8001")
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--duration", type=int, default=30)
    args = parser.parse_args()

    print("=" * 60)
    print("AIMP LOAD TEST")
    print(f"Host: {args.host} | Users: {args.users} | Duration: {args.duration}s")
    print("=" * 60)

    import threading
    results = []
    threads = []
    start = time.time()

    for i in range(args.users):
        t = threading.Thread(target=worker, args=(args.host, i, args.duration, results))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    total_time = time.time() - start
    total_reqs = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = total_reqs - passed
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] > 0]
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

    print(f"\n{'=' * 60}")
    print(f"Results: {total_reqs} requests in {total_time:.1f}s")
    print(f"Pass: {passed} | Fail: {failed} | RPS: {total_reqs / total_time:.1f}")
    print(f"Avg latency: {avg_lat:.1f}ms | P95: {p95_lat:.1f}ms")

    # Per-endpoint stats
    print(f"\nPer-endpoint:")
    for ep in ENDPOINTS:
        ep_results = [r for r in results if r["endpoint"] == ep]
        ep_pass = sum(1 for r in ep_results if r["ok"])
        print(f"  {ep:30s} {ep_pass}/{len(ep_results)} OK")

    # Pass/fail verdict
    if failed / total_reqs < 0.05 and p95_lat < 2000:
        print(f"\nPASS: System handles {args.users} concurrent users")
        return 0
    else:
        print(f"\nFAIL: Error rate or latency too high")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
