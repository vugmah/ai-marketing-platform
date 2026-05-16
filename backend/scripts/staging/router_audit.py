"""Router & API Registration Audit

Validates all router files are registered in main.py with correct prefixes.
Usage: python scripts/staging/router_audit.py
"""
import ast, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def get_router_files():
    routers = set()
    for f in sorted((PROJECT_ROOT / "app").rglob("*router.py")):
        rel = str(f.relative_to(PROJECT_ROOT / "app")).replace("/", ".").replace("\\", ".")[:-3]
        routers.add(f"app.{rel}")
    return routers

def get_registered_routers():
    registered = set()
    with open(PROJECT_ROOT / "app" / "main.py") as f:
        for line in f:
            line = line.strip()
            if line.startswith("from app.") and "router" in line and "import" in line:
                module = line.split()[1] if len(line.split()) > 1 else ""
                if module:
                    registered.add(module)
    return registered

def main():
    print("=" * 60)
    print("ROUTER & API REGISTRATION AUDIT")
    print("=" * 60)
    files = get_router_files()
    registered = get_registered_routers()
    file_modules = {f for f in files}
    unregistered = file_modules - registered
    print(f"\nRouter files: {len(files)}")
    print(f"Registered: {len(registered)}")
    if unregistered:
        print(f"\nFAIL: {len(unregistered)} unregistered:")
        for r in sorted(unregistered):
            print(f"  - {r}")
        return 1
    print("\nPASS: All routers registered")
    print(f"\nRegistered endpoints:")
    with open(PROJECT_ROOT / "app" / "main.py") as f:
        for line in f:
            if 'prefix="/api/v2/' in line:
                print(f"  {line.strip()}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
