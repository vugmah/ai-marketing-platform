"""Security & Penetration Validation

Scans for common security issues without requiring external tools.
Usage: python scripts/staging/security_validation.py
"""
import ast, os, sys, re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def scan_secrets():
    """Scan for hardcoded secrets."""
    issues = []
    patterns = [
        (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
        (r'secret\s*=\s*["\'][^"\']+["\']', "Hardcoded secret"),
        (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
        (r'sk-[a-zA-Z0-9]{20,}', "OpenAI API key leak"),
        (r'AKIA[0-9A-Z]{16}', "AWS access key"),
    ]
    exempt = ['test', 'example', 'dummy', 'placeholder', 'changeme', 'script']

    for f in (PROJECT_ROOT / "app").rglob("*.py"):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
            for i, line in enumerate(content.split('\n'), 1):
                for pattern, desc in patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        if not any(e in line.lower() for e in exempt + ['env', 'config', 'settings', 'getenv']):
                            rel = str(f.relative_to(PROJECT_ROOT))
                            issues.append(f"{rel}:{i}: {desc}")
        except:
            pass
    return issues


def scan_sql_injection():
    """Scan for raw SQL that might be injectable."""
    issues = []
    for f in (PROJECT_ROOT / "app").rglob("*.py"):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
            if 'f"SELECT' in content or 'f"INSERT' in content or 'f"UPDATE' in content or 'f"DELETE' in content:
                rel = str(f.relative_to(PROJECT_ROOT))
                issues.append(f"{rel}: f-string SQL query (potential injection)")
            if 'execute("' in content and '%' in content:
                rel = str(f.relative_to(PROJECT_ROOT))
                issues.append(f"{rel}: String-format SQL (potential injection)")
        except:
            pass
    return issues


def scan_dangerous_functions():
    """Scan for dangerous Python functions."""
    issues = []
    dangerous = ['eval(', 'exec(', 'os.system(', 'subprocess.call(', 'pickle.loads(', '__import__(']
    for f in (PROJECT_ROOT / "app").rglob("*.py"):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
            for bad in dangerous:
                if bad in content:
                    rel = str(f.relative_to(PROJECT_ROOT))
                    issues.append(f"{rel}: Uses {bad}")
        except:
            pass
    return issues


def check_cors_config():
    """Check CORS configuration."""
    issues = []
    main_py = PROJECT_ROOT / "app" / "main.py"
    with open(main_py) as f:
        content = f.read()
    if "CORSMiddleware" in content:
        if "*" in content and "allow_origins" in content:
            issues.append("main.py: CORS allows wildcard origin (*)")
    return issues


def main():
    print("=" * 60)
    print("SECURITY & PENETRATION VALIDATION")
    print("=" * 60)

    all_issues = []

    print("\n--- 1. Secret Scan ---")
    secrets = scan_secrets()
    if secrets:
        all_issues.extend(secrets)
        for s in secrets[:10]:
            print(f"  CRIT: {s}")
        if len(secrets) > 10:
            print(f"  ... and {len(secrets) - 10} more")
    else:
        print("  OK: No hardcoded secrets found")

    print("\n--- 2. SQL Injection Scan ---")
    sql = scan_sql_injection()
    if sql:
        all_issues.extend(sql)
        for s in sql[:5]:
            print(f"  WARN: {s}")
    else:
        print("  OK: No raw SQL injection patterns")

    print("\n--- 3. Dangerous Functions ---")
    danger = scan_dangerous_functions()
    if danger:
        all_issues.extend(danger)
        for d in danger[:5]:
            print(f"  WARN: {d}")
    else:
        print("  OK: No dangerous functions")

    print("\n--- 4. CORS Configuration ---")
    cors = check_cors_config()
    if cors:
        all_issues.extend(cors)
        for c in cors:
            print(f"  WARN: {c}")
    else:
        print("  OK: CORS configured")

    print(f"\n{'=' * 60}")
    if all_issues:
        print(f"RESULT: {len(all_issues)} issue(s) - REVIEW REQUIRED")
        return 1
    print("RESULT: PASS - No critical security issues")
    return 0


if __name__ == "__main__":
    sys.exit(main())
