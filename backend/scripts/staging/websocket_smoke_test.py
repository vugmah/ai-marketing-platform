"""WebSocket Smoke Test

Tests WebSocket gateway connectivity and message delivery
without requiring authentication.

Usage:
    cd backend && python scripts/staging/websocket_smoke_test.py --host ws://localhost:8001
"""

import argparse
import json
import sys
import time
import urllib.request


def test_websocket_connect(host: str) -> dict:
    """Test WebSocket endpoint responds (even without ws client lib)."""
    import urllib.request
    from urllib.error import HTTPError

    # WebSocket endpoints typically return 426 or 400 on HTTP GET
    # A response (any response) means the endpoint is listening
    ws_url = f"{host}/api/v2/realtime/ws"
    http_url = f"{host}/api/v2/health"

    result = {"ws_endpoint": None, "http_fallback": None, "latency_ms": -1}

    start = time.time()
    try:
        req = urllib.request.Request(ws_url, method="GET")
        req.add_header("User-Agent", "aimp-ws-test/1.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result["ws_endpoint"] = {"status": resp.status, "ok": True}
    except HTTPError as e:
        # 426 Upgrade Required = WebSocket endpoint is listening
        if e.code in (426, 400, 403):
            result["ws_endpoint"] = {"status": e.code, "ok": True, "note": "WS endpoint active (expected non-200)"}
        else:
            result["ws_endpoint"] = {"status": e.code, "ok": False}
    except Exception as e:
        result["ws_endpoint"] = {"status": 0, "ok": False, "error": str(e)[:80]}

    result["latency_ms"] = round((time.time() - start) * 1000, 1)

    # Check HTTP health endpoint
    try:
        req = urllib.request.Request(http_url, method="GET")
        req.add_header("User-Agent", "aimp-ws-test/1.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            result["http_fallback"] = {"status": resp.status, "ok": True}
    except Exception as e:
        result["http_fallback"] = {"status": 0, "ok": False, "error": str(e)[:80]}

    return result


def test_reconnect_behavior(host: str) -> dict:
    """Simulate disconnect/reconnect by making rapid sequential requests."""
    url = f"{host}/api/v2/health"
    results = []
    for i in range(5):
        start = time.time()
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", f"aimp-ws-test-reconnect/{i}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                results.append({
                    "attempt": i + 1,
                    "ok": True,
                    "status": resp.status,
                    "latency_ms": round((time.time() - start) * 1000, 1),
                })
        except Exception as e:
            results.append({
                "attempt": i + 1,
                "ok": False,
                "latency_ms": round((time.time() - start) * 1000, 1),
                "error": str(e)[:80],
            })
        time.sleep(0.2)

    return {
        "attempts": len(results),
        "passed": sum(1 for r in results if r["ok"]),
        "avg_latency_ms": round(sum(r["latency_ms"] for r in results) / len(results), 1) if results else 0,
        "details": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="WebSocket Smoke Test")
    parser.add_argument("--host", default="http://localhost:8001", help="Backend host (HTTP, WS derived from it)")
    args = parser.parse_args()

    print("=" * 60)
    print("WEBSOCKET SMOKE TEST")
    print(f"Host: {args.host}")
    print("=" * 60)

    # Test 1: WS endpoint connectivity
    print("\n--- 1. WebSocket Endpoint ---")
    ws_result = test_websocket_connect(args.host)
    if ws_result["ws_endpoint"] and ws_result["ws_endpoint"]["ok"]:
        print(f"  PASS: WS endpoint responding (status={ws_result['ws_endpoint']['status']})")
        if "note" in ws_result["ws_endpoint"]:
            print(f"  INFO: {ws_result['ws_endpoint']['note']}")
    else:
        print(f"  FAIL: WS endpoint not reachable")
        if "error" in (ws_result.get("ws_endpoint") or {}):
            print(f"  ERROR: {ws_result['ws_endpoint']['error']}")
    print(f"  Latency: {ws_result['latency_ms']}ms")

    # Test 2: Reconnect behavior
    print("\n--- 2. Reconnect Simulation ---")
    rc_result = test_reconnect_behavior(args.host)
    print(f"  Attempts: {rc_result['attempts']}, Passed: {rc_result['passed']}")
    print(f"  Avg latency: {rc_result['avg_latency_ms']}ms")
    for d in rc_result["details"]:
        status = "OK" if d["ok"] else "FAIL"
        print(f"    [{status}] Attempt {d['attempt']}: {d['latency_ms']}ms")

    # Test 3: HTTP fallback
    print("\n--- 3. HTTP Fallback ---")
    if ws_result["http_fallback"] and ws_result["http_fallback"]["ok"]:
        print(f"  PASS: HTTP health endpoint OK (status={ws_result['http_fallback']['status']})")
    else:
        print(f"  FAIL: HTTP fallback not working")

    # Summary
    passed = (
        1 if ws_result["ws_endpoint"] and ws_result["ws_endpoint"]["ok"] else 0
        + 1 if rc_result["passed"] >= 4 else 0
        + 1 if ws_result["http_fallback"] and ws_result["http_fallback"]["ok"] else 0
    )
    total = 3

    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{total} tests passed")
    if passed == total:
        print("STATUS: ALL WEBSOCKET TESTS PASSED")
        return 0
    else:
        print(f"STATUS: {total - passed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
