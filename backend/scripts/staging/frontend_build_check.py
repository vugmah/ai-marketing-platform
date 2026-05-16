"""Frontend Build Validation

Checks frontend for:
- Required environment variables
- Missing API endpoint mappings
- Type definition completeness
- Build configuration

Usage:
    cd frontend && python ../backend/scripts/staging/frontend_build_check.py
"""

import ast
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def check_types_complete() -> list:
    """Check if TypeScript types are defined for API responses."""
    issues = []
    types_dir = FRONTEND_DIR / "src" / "types"
    if not types_dir.exists():
        issues.append("types/ directory does not exist")
        return issues

    required_types = [
        "auth", "company", "branch", "user", "analytics",
        "campaign", "follower", "ai", "erp", "report",
    ]
    for t in required_types:
        type_file = types_dir / f"{t}.ts"
        if not type_file.exists():
            issues.append(f"Missing type file: types/{t}.ts")

    return issues


def check_api_client() -> list:
    """Check API client configuration."""
    issues = []
    api_file = FRONTEND_DIR / "src" / "api" / "index.ts"
    if not api_file.exists():
        issues.append("API client (src/api/index.ts) not found")
        return issues

    with open(api_file, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'baseURL' not in content and 'BASE_URL' not in content:
        issues.append("API client missing baseURL configuration")
    if 'axios' not in content.lower() and 'fetch' not in content.lower():
        issues.append("API client missing HTTP client (axios/fetch)")

    return issues


def check_endpoint_coverage() -> list:
    """Check which backend endpoints have frontend mappings."""
    issues = []

    # Get all backend router registrations
    main_py = PROJECT_ROOT / "backend" / "app" / "main.py"
    if not main_py.exists():
        return ["Cannot find backend main.py"]

    with open(main_py, 'r') as f:
        main_content = f.read()

    # Extract registered paths
    import re
    registered_paths = re.findall(r'prefix="(/api/v2/[^"]+)"', main_content)

    # Search frontend for API path references
    src_dir = FRONTEND_DIR / "src"
    if not src_dir.exists():
        return ["Frontend src/ directory not found"]

    frontend_content = ""
    for f in src_dir.rglob("*.ts"):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                frontend_content += fh.read() + "\n"
        except:
            pass
    for f in src_dir.rglob("*.tsx"):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                frontend_content += fh.read() + "\n"
        except:
            pass

    uncovered = []
    for path in registered_paths:
        # Check if frontend references this path
        path_simple = path.replace("/api/v2/", "")
        if path_simple not in frontend_content and path not in frontend_content:
            uncovered.append(path)

    if uncovered:
        issues.append(f"{len(uncovered)} backend endpoints not referenced in frontend:")
        for u in uncovered:
            issues.append(f"  - {u}")

    return issues


def check_package_json() -> list:
    """Check package.json for required scripts and deps."""
    issues = []
    pkg_file = FRONTEND_DIR / "package.json"
    if not pkg_file.exists():
        return ["package.json not found"]

    with open(pkg_file, 'r') as f:
        pkg = json.load(f)

    scripts = pkg.get("scripts", {})
    if "build" not in scripts:
        issues.append("Missing 'build' script in package.json")
    if "dev" not in scripts and "start" not in scripts:
        issues.append("Missing 'dev' or 'start' script in package.json")

    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    required = ["react", "react-dom", "react-router-dom", "typescript"]
    for dep in required:
        if dep not in deps:
            issues.append(f"Missing dependency: {dep}")

    return issues


def main() -> int:
    print("=" * 60)
    print("FRONTEND BUILD VALIDATION")
    print("=" * 60)

    if not FRONTEND_DIR.exists():
        print(f"ERROR: Frontend directory not found at {FRONTEND_DIR}")
        return 1

    all_issues = []

    print("\n--- 1. Package.json ---")
    issues = check_package_json()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  WARN: {i}")
    else:
        print("  OK: package.json valid")

    print("\n--- 2. Type Definitions ---")
    issues = check_types_complete()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  WARN: {i}")
    else:
        print("  OK: All type files present")

    print("\n--- 3. API Client ---")
    issues = check_api_client()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  WARN: {i}")
    else:
        print("  OK: API client configured")

    print("\n--- 4. Endpoint Coverage ---")
    issues = check_endpoint_coverage()
    if issues:
        all_issues.extend(issues)
        for i in issues:
            print(f"  {i}")
    else:
        print("  OK: All endpoints covered")

    print(f"\n{'=' * 60}")
    print(f"Total issues: {len(all_issues)}")

    if all_issues:
        print("RESULT: REVIEW REQUIRED")
        return 1
    else:
        print("RESULT: PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
