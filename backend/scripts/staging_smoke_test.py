"""Staging Smoke Test - End-to-end API validation

Runs a sequence of API calls against staging to verify core flows work.
Usage: python scripts/staging_smoke_test.py --host http://localhost:8001

Exit codes:
    0 - All smoke tests passed
    1 - One or more tests failed
"""

import argparse
import json
import sys
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError


class SmokeTester:
    def __init__(self, host: str):
        self.host = host.rstrip("/")
        self.token = None
        self.results = []

    def _req(self, method: str, path: str, data: dict = None, auth: bool = False) -> dict:
        url = f"{self.host}{path}"
        body = json.dumps(data).encode() if data else None
        req = Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "aimp-smoke-test/2.0")
        if auth and self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                return {"ok": True, "status": resp.status, "body": body[:500]}
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore") if hasattr(e, "read") else ""
            return {"ok": False, "status": e.code, "body": body[:500], "error": str(e)}
        except Exception as e:
            return {"ok": False, "status": 0, "body": "", "error": str(e)}

    def _test(self, name: str, path: str, method: str = "GET", data: dict = None, auth: bool = False) -> bool:
        result = self._req(method, path, data, auth)
        ok = result["ok"]
        self.results.append((name, ok, result["status"]))
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name:40s} HTTP {result['status']}")
        if not ok and "error" in result:
            print(f"        -> {result['error'][:80]}")
        return ok

    def run_all(self) -> bool:
        print("=" * 60)
        print("AIMP STAGING SMOKE TEST")
        print(f"Host: {self.host}")
        print("=" * 60)

        # Phase 1: Health endpoints (no auth)
        print("\n--- Health Endpoints ---")
        self._test("API Root", "/api/v2/health")
        self._test("DB Health", "/api/v2/health/db")
        self._test("Redis Health", "/api/v2/health/redis")
        self._test("Queue Health", "/api/v2/health/queue")
        self._test("Storage Health", "/api/v2/health/storage")
        self._test("API Docs (Swagger)", "/docs")

        # Phase 2: Auth flow
        print("\n--- Auth Flow ---")
        test_email = f"smoke_{uuid.uuid4().hex[:8]}@test.local"
        test_pass = "SmokeTestPass123!"

        register = self._test("User Registration", "/api/v2/auth/register", "POST", {
            "email": test_email,
            "password": test_pass,
            "full_name": "Smoke Test User",
            "company_name": "Smoke Corp",
        })

        login = self._test("User Login", "/api/v2/auth/login", "POST", {
            "email": test_email,
            "password": test_pass,
        })

        # Extract token from login response
        if login:
            try:
                login_body = json.loads(self._req("POST", "/api/v2/auth/login", {
                    "email": test_email, "password": test_pass,
                })["body"])
                self.token = login_body.get("access_token") or login_body.get("token", "")
                print(f"        Token extracted: {self.token[:20]}...")
            except:
                self.token = None

        if self.token:
            self._test("Get Current User", "/api/v2/auth/me", auth=True)

        # Phase 3: Core CRUD
        print("\n--- Core Endpoints ---")
        if self.token:
            self._test("Company List", "/api/v2/companies", auth=True)
            self._test("Dashboard Analytics", "/api/v2/analytics/summary", auth=True)
            self._test("Follower Overview", "/api/v2/followers/overview", auth=True)

        # Phase 4: Governance (admin)
        print("\n--- Governance Endpoints ---")
        self._test("Observability Health Score", "/api/v2/observability/health-score", auth=True)
        self._test("Tenant Quota Check", "/api/v2/tenant-governance/quota/check?resource_type=ai_tokens_hour&requested=1", auth=True)
        self._test("Release Notes", "/api/v2/rollout/release-notes", auth=True)
        self._test("Incident Dashboard", "/api/v2/incidents/dashboard/recovery", auth=True)

        # Phase 5: AI endpoints
        print("\n--- AI Endpoints ---")
        if self.token:
            self._test("AI Safety Policies", "/api/v2/ai-safety/policies", auth=True)
            self._test("AI Cost Budget", "/api/v2/ai-cost/budget", auth=True)
            self._test("AI Model List", "/api/v2/ai-cost/models", auth=True)

        # Summary
        passed = sum(1 for _, ok, _ in self.results if ok)
        total = len(self.results)
        print(f"\n{'=' * 60}")
        print(f"Results: {passed}/{total} tests passed")

        if passed == total:
            print("STATUS: ALL SMOKE TESTS PASSED")
            return True
        else:
            print(f"STATUS: {total - passed} TEST(S) FAILED")
            return False


def main() -> int:
    parser = argparse.ArgumentParser(description="AIMP Staging Smoke Test")
    parser.add_argument("--host", default="http://localhost:8001", help="Backend host")
    args = parser.parse_args()

    tester = SmokeTester(args.host)
    success = tester.run_all()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
