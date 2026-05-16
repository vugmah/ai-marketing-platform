"""Forbidden mock/demo detector - Scans for mock/demo/placeholder code.

Usage:
    cd backend && python scripts/quality/forbidden_mock_detector.py

Exit codes:
    0 - No forbidden patterns found
    1 - Mock/demo code detected
"""

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Patterns that indicate mock/demo code in services/models
FORBIDDEN_PATTERNS = [
    ("pass", "Empty method body (pass)"),
    ("# TODO", "Unfinished TODO"),
    ("# FIXME", "Unfinished FIXME"),
    ("raise NotImplementedError", "Not implemented"),
    ("NotImplementedError(", "Not implemented"),
    ("mock", "Mock reference"),
    ("placeholder", "Placeholder"),
    ("dummy", "Dummy data"),
    ("hardcoded", "Hardcoded value"),
    ("# MOCK", "Mock marker"),
]

# Files exempt from checks (test files, config, etc.)
EXEMPT_PATHS = ["tests/", "alembic/", "scripts/", "__pycache__", "settings.py", "config.py"]


def scan_file(filepath: Path) -> list:
    """Scan a single file for forbidden patterns."""
    issues = []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, PermissionError):
        return issues
    
    for lineno, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comments that are just markers
        for pattern, reason in FORBIDDEN_PATTERNS:
            if pattern.lower() in stripped.lower():
                # Skip false positives in comments about mocking
                if pattern == "pass" and (stripped.startswith("#") or "password" in stripped.lower() or "bypass" in stripped.lower()):
                    continue
                if pattern == "mock" and ("mockApi" in stripped or "mock_" in stripped or "unmock" in stripped.lower()):
                    continue
                issues.append((lineno, pattern, reason, stripped[:80]))
    
    return issues


def main() -> int:
    print("=" * 60)
    print("FORBIDDEN MOCK/DEMO DETECTOR")
    print("=" * 60)
    
    total_issues = 0
    files_with_issues = 0
    
    for py_file in sorted(PROJECT_ROOT.rglob("*.py")):
        # Skip exempt paths
        rel = str(py_file.relative_to(PROJECT_ROOT))
        if any(exempt in rel for exempt in EXEMPT_PATHS):
            continue
        
        issues = scan_file(py_file)
        if issues:
            files_with_issues += 1
            total_issues += len(issues)
            print(f"\n  {rel}:")
            for lineno, pattern, reason, line in issues:
                print(f"    L{lineno}: [{reason}] {line}")
    
    print(f"\n{'=' * 60}")
    print(f"Files scanned: {len(list(PROJECT_ROOT.rglob('*.py')))}")
    print(f"Files with issues: {files_with_issues}")
    print(f"Total issues: {total_issues}")
    
    if total_issues > 0:
        print(f"\nRESULT: FAIL - {total_issues} mock/demo patterns found.")
        return 1
    else:
        print(f"\nRESULT: PASS - No forbidden patterns found.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
