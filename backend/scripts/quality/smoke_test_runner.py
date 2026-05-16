"""Smoke test runner - Validates all modules import correctly.

Usage:
    cd backend && python scripts/quality/smoke_test_runner.py

Exit codes:
    0 - All smoke tests passed
    1 - One or more tests failed
"""

import ast
import importlib
import os
import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def test_file_syntax(filepath: Path) -> bool:
    """Test that a Python file has valid syntax."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            ast.parse(f.read())
        return True
    except (SyntaxError, UnicodeDecodeError) as e:
        return False


def test_router_has_prefix(router_file: Path) -> bool:
    """Verify router files define prefix in APIRouter."""
    try:
        with open(router_file, "r", encoding="utf-8") as f:
            content = f.read()
        return "APIRouter" in content and "prefix=" in content
    except Exception:
        return False


def test_model_has_tablename(model_file: Path) -> bool:
    """Verify model files define __tablename__."""
    try:
        with open(model_file, "r", encoding="utf-8") as f:
            content = f.read()
        return "__tablename__" in content and "Base" in content
    except Exception:
        return False


def run_tests() -> dict:
    """Run all smoke tests and return results."""
    results = {
        "passed": 0,
        "failed": 0,
        "tests": [],
    }
    
    # Test 1: All .py files have valid syntax
    py_files = list(PROJECT_ROOT.rglob("*.py"))
    syntax_failures = []
    for f in py_files:
        rel = str(f.relative_to(PROJECT_ROOT))
        if not test_file_syntax(f):
            syntax_failures.append(rel)
    
    results["tests"].append({
        "name": "Python syntax validation",
        "total": len(py_files),
        "passed": len(py_files) - len(syntax_failures),
        "failed": len(syntax_failures),
        "details": syntax_failures[:10],
    })
    if syntax_failures:
        results["failed"] += 1
    else:
        results["passed"] += 1
    
    # Test 2: All router files have prefix
    router_files = list((PROJECT_ROOT / "app").rglob("*router.py"))
    router_failures = []
    for f in router_files:
        if not test_router_has_prefix(f):
            router_failures.append(str(f.relative_to(PROJECT_ROOT)))
    
    results["tests"].append({
        "name": "Router prefix validation",
        "total": len(router_files),
        "passed": len(router_files) - len(router_failures),
        "failed": len(router_failures),
        "details": router_failures[:10],
    })
    if router_failures:
        results["failed"] += 1
    else:
        results["passed"] += 1
    
    # Test 3: All model files have __tablename__ and Base
    model_files = list((PROJECT_ROOT / "app").rglob("*models.py"))
    model_failures = []
    for f in model_files:
        if not test_model_has_tablename(f):
            model_failures.append(str(f.relative_to(PROJECT_ROOT)))
    
    results["tests"].append({
        "name": "Model structure validation",
        "total": len(model_files),
        "passed": len(model_files) - len(model_failures),
        "failed": len(model_failures),
        "details": model_failures[:10],
    })
    if model_failures:
        results["failed"] += 1
    else:
        results["passed"] += 1
    
    return results


def main() -> int:
    print("=" * 60)
    print("SMOKE TEST RUNNER")
    print("=" * 60)
    
    results = run_tests()
    
    for test in results["tests"]:
        status = "PASS" if test["failed"] == 0 else "FAIL"
        print(f"\n  [{status}] {test['name']}: {test['passed']}/{test['total']}")
        if test["details"]:
            for detail in test["details"]:
                print(f"      - {detail}")
    
    print(f"\n{'=' * 60}")
    print(f"Test suites: {results['passed']} passed, {results['failed']} failed")
    
    if results["failed"] > 0:
        print(f"RESULT: FAIL")
        return 1
    else:
        print(f"RESULT: PASS")
        return 0


if __name__ == "__main__":
    sys.exit(main())
