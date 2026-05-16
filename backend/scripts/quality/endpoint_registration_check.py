"""Endpoint registration check - Verifies all routers are registered in main.py.

Usage:
    cd backend && python scripts/quality/endpoint_registration_check.py

Exit codes:
    0 - All routers registered
    1 - Unregistered routers found
"""

import ast
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_router_files() -> set:
    """Find all *router.py files."""
    routers_dir = PROJECT_ROOT / "app"
    router_files = set()
    for f in routers_dir.rglob("*router.py"):
        # Convert path to import notation: app/ai/router.py -> app.ai.router
        rel = f.relative_to(PROJECT_ROOT).with_suffix("")
        module_path = str(rel).replace(os.sep, ".")
        # Check if it defines a router variable
        try:
            with open(f, "r", encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and "router" in target.id:
                            router_files.add(module_path)
                            break
        except (SyntaxError, UnicodeDecodeError):
            pass
    return router_files


def get_registered_routers() -> set:
    """Find all router imports in main.py."""
    main_file = PROJECT_ROOT / "app" / "main.py"
    registered = set()
    with open(main_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Match: from app.xxx.router import router as xxx_router
            if line.startswith("from app.") and "router" in line and "import" in line:
                # Extract module path: from app.ai.router -> app.ai.router
                parts = line.split()
                if len(parts) >= 2:
                    module = parts[1]  # app.xxx.router
                    registered.add(module)
    return registered


def main() -> int:
    print("=" * 60)
    print("ENDPOINT REGISTRATION CHECK")
    print("=" * 60)
    
    router_files = get_router_files()
    registered = get_registered_routers()
    
    # Find router modules from files
    router_modules = {f for f in router_files}
    
    print(f"\nRouter files found:     {len(router_modules)}")
    print(f"Routers in main.py:     {len(registered)}")
    
    # Check which are registered
    unregistered = router_modules - registered
    
    if unregistered:
        print(f"\nFAIL: {len(unregistered)} router files NOT registered in main.py:")
        for r in sorted(unregistered):
            print(f"  - {r}")
        print(f"\nAdd to main.py:")
        for r in sorted(unregistered):
            name = r.split(".")[-2] if len(r.split(".")) > 2 else "router"
            print(f"  from {r} import router as {name}_router")
        return 1
    else:
        print(f"\nPASS: All {len(router_modules)} router files are registered in main.py.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
