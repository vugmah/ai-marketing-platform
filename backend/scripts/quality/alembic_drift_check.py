"""Alembic drift check - Compares SQLAlchemy models against migrations.

Usage:
    cd backend && python scripts/quality/alembic_drift_check.py

Exit codes:
    0 - No drift detected
    1 - Schema drift found (tables missing from migrations)
    2 - Configuration error
"""

import ast
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


def get_tables_from_models() -> set:
    """Extract all __tablename__ declarations from model files."""
    models_dir = PROJECT_ROOT / "app"
    tables = set()
    
    for model_file in models_dir.rglob("*models.py"):
        try:
            with open(model_file, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name) and target.id == "__tablename__":
                                    if isinstance(item.value, ast.Constant) and isinstance(item.value.value, str):
                                        tables.add(item.value.value)
                                    elif isinstance(item.value, ast.Str):
                                        tables.add(item.value.s)
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"  WARNING: Could not parse {model_file}: {e}")
    
    return tables


def get_tables_from_migrations() -> set:
    """Extract all table names from op.create_table calls in migrations."""
    migrations_dir = PROJECT_ROOT / "alembic" / "versions"
    tables = set()
    
    for migration_file in sorted(migrations_dir.glob("*.py")):
        try:
            with open(migration_file, "r", encoding="utf-8") as f:
                content = f.read()
            # Find op.create_table("tablename"
            import re
            for match in re.finditer(r'op\.create_table\(\s*["\']([^"\']+)["\']', content):
                tables.add(match.group(1))
        except Exception as e:
            print(f"  WARNING: Could not read {migration_file}: {e}")
    
    return tables


def main() -> int:
    print("=" * 60)
    print("ALEMBIC DRIFT CHECK")
    print("=" * 60)
    
    model_tables = get_tables_from_models()
    migration_tables = get_tables_from_migrations()
    
    print(f"\nTables in SQLAlchemy models:  {len(model_tables)}")
    print(f"Tables in Alembic migrations: {len(migration_tables)}")
    
    # Tables in models but not in migrations (DRIFT)
    missing_from_migrations = model_tables - migration_tables
    # Tables in migrations but not in models (orphaned)
    orphaned_in_migrations = migration_tables - model_tables
    
    print(f"\n{'=' * 60}")
    
    if missing_from_migrations:
        print(f"FAIL: {len(missing_from_migrations)} tables in models but NOT in migrations:")
        for t in sorted(missing_from_migrations):
            print(f"  - {t}")
    else:
        print("PASS: All model tables are covered by migrations.")
    
    if orphaned_in_migrations:
        print(f"\nWARN: {len(orphaned_in_migrations)} tables in migrations but NOT in models (orphaned):")
        for t in sorted(orphaned_in_migrations):
            print(f"  - {t}")
    
    # Summary
    coverage_pct = len(model_tables & migration_tables) / len(model_tables) * 100 if model_tables else 0
    print(f"\n{'=' * 60}")
    print(f"Migration coverage: {coverage_pct:.1f}% ({len(model_tables & migration_tables)}/{len(model_tables)})")
    
    if missing_from_migrations:
        print(f"RESULT: FAIL - Schema drift detected!")
        return 1
    else:
        print(f"RESULT: PASS - No schema drift.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
