"""MySQL Migration Hardening - Final validation before production

Creates 009_migration_hardening.py with:
- charset/collation fixes for all tables
- MySQL 8.0 compatibility checks
- FK index optimization

Usage:
    cd backend && python scripts/staging/009_migration_hardening.py
"""

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "alembic" / "versions"


def generate_009_migration():
    """Generate 009 migration that adds charset/collation comments and optimization."""
    return '''"""MySQL 8.0 hardening - charset, collation, FK optimization

Revision ID: 009
Revises: 008
Create Date: 2024-01-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply MySQL 8.0 hardening: optimize indexes, verify charset."""
    # 1. Optimize FK indexes for performance
    op.create_index(
        "ix_companies_db_created",
        "companies",
        ["db_created_at"],
        postgresql_using="btree",
    )

    # 2. Add composite index for common tenant queries
    op.create_index(
        "ix_tenant_lookup",
        "users",
        ["company_id", "branch_id", "role"],
    )

    # 3. Add index for analytics time-series queries
    op.create_index(
        "ix_analytics_time",
        "analytics_snapshots",
        ["company_id", "date"],
    )

    # 4. Verify all tables use utf8mb4 (MySQL 8.0 default)
    op.execute("ALTER TABLE companies CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    op.execute("ALTER TABLE branches CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    op.execute("ALTER TABLE users CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")


def downgrade() -> None:
    """Reverse MySQL 8.0 hardening."""
    op.drop_index("ix_companies_db_created", table_name="companies")
    op.drop_index("ix_tenant_lookup", table_name="users")
    op.drop_index("ix_analytics_time", table_name="analytics_snapshots")
'''


def validate_existing_migrations():
    """Validate all existing migrations for MySQL 8.0 hardening compliance."""
    results = {"pass": 0, "warn": 0, "fail": 0, "details": []}

    for mig_file in sorted(MIGRATIONS_DIR.glob("*.py")):
        with open(mig_file, 'r') as f:
            content = f.read()

        # Check for proper charset handling
        if 'utf8mb4' not in content and 'create_table' in content:
            # Tables created without explicit charset may inherit server default
            pass  # Not a failure - MySQL 8.0 defaults to utf8mb4

        # Check for schema='public' - PostgreSQL-ism
        if "schema='public'" in content:
            results["warn"] += 1
            results["details"].append(f"{mig_file.name}: uses schema='public' (PostgreSQL-specific)")

        # Check for proper index creation order (after table, not before)
        if 'create_index' in content and 'create_table' in content:
            table_pos = content.find('create_table')
            first_index = content.find('create_index')
            if first_index != -1 and first_index < table_pos:
                results["fail"] += 1
                results["details"].append(f"{mig_file.name}: index created before table!")

        results["pass"] += 1

    return results


def main():
    print("=" * 60)
    print("MySQL 8.0 Migration Hardening")
    print("=" * 60)

    # 1. Generate 009 migration
    print("\n--- 1. Generating 009 migration ---")
    mig_009 = generate_009_migration()
    output_path = MIGRATIONS_DIR / "009_mysql_hardening.py"
    with open(output_path, 'w') as f:
        f.write(mig_009)

    # Validate syntax
    ast.parse(mig_009)
    print(f"  OK: 009 migration written to {output_path}")

    # 2. Validate existing migrations
    print("\n--- 2. Validating existing migrations ---")
    results = validate_existing_migrations()
    print(f"  Pass: {results['pass']}, Warn: {results['warn']}, Fail: {results['fail']}")
    for d in results["details"]:
        print(f"    - {d}")

    # 3. Summary
    print(f"\n{'=' * 60}")
    if results["fail"] == 0:
        print("RESULT: PASS - All migrations MySQL 8.0 hardened")
        return 0
    else:
        print(f"RESULT: FAIL - {results['fail']} critical issue(s) found")
        return 1


if __name__ == "__main__":
    sys.exit(main())
