#!/usr/bin/env python3
"""
AI Marketing Platform v2.0 - Staging DB Migration Script

This script performs a controlled migration on the Railway staging MySQL database.
It requires a valid Railway API token with access to the project.

Usage:
    export RAILWAY_TOKEN="your-fresh-token"
    python scripts/run_staging_migration.py

What it does:
1. Authenticates with Railway CLI
2. Retrieves MySQL connection details
3. Checks current DB state (alembic_version, partial tables)
4. Drops partial AI tables from previous failed migrations
5. Runs 'alembic upgrade head' via sync engine
6. Verifies migration success (alembic_version = 011)
7. Restores database.py and env.py to async originals
8. Reports final status
"""

import json
import os
import subprocess
import sys
import time


def run_cmd(cmd, cwd=None, env=None, check=True):
    """Run a shell command and return stdout."""
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=merged_env,
    )
    if check and result.returncode != 0:
        print(f"  [ERROR] Command failed (code {result.returncode}): {cmd}")
        print(f"  stderr: {result.stderr[:500]}")
        return None
    return result.stdout.strip()


def railway_login(token):
    """Login to Railway CLI with token."""
    print("\n[1/8] Authenticating with Railway CLI...")
    # Clear any existing auth
    run_cmd("rm -rf ~/.railway")
    result = run_cmd(f"npx @railway/cli@latest login --browserless", env={"RAILWAY_TOKEN": token})
    if result is None:
        print("  [FAIL] Railway login failed. Token may be expired or invalid.")
        print("  Get a fresh token from: https://railway.com/account/tokens")
        return False
    print("  [OK] Railway login successful")
    return True


def get_mysql_vars(token, project_dir):
    """Get MySQL connection details from Railway."""
    print("\n[2/8] Retrieving MySQL connection details from Railway...")

    # Try to get variables using railway run
    result = run_cmd(
        "npx @railway/cli@latest variables --json",
        cwd=project_dir,
        env={"RAILWAY_TOKEN": token},
        check=False,
    )

    if result:
        try:
            vars_json = json.loads(result)
            mysql_vars = {k: v for k, v in vars_json.items() if "MYSQL" in k.upper() or k.upper() == "DATABASE_URL"}
            if mysql_vars:
                print(f"  [OK] Found {len(mysql_vars)} DB-related variables")
                return vars_json
        except json.JSONDecodeError:
            pass

    # Fallback: try service variables
    result = run_cmd(
        "npx @railway/cli@latest service --json",
        cwd=project_dir,
        env={"RAILWAY_TOKEN": token},
        check=False,
    )

    print("  [WARN] Could not retrieve variables via CLI. Trying public TCP proxy...")
    return None


def test_mysql_connection(host, port, user, password, database):
    """Test MySQL connection using pymysql."""
    print(f"\n[3/8] Testing MySQL connection to {host}:{port}...")
    try:
        import pymysql
        conn = pymysql.connect(
            host=host,
            port=int(port),
            user=user,
            password=password,
            database=database,
            connect_timeout=10,
            ssl_disabled=True,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        conn.close()
        print("  [OK] MySQL connection successful")
        return True
    except ImportError:
        print("  [ERROR] pymysql not installed. Run: pip install pymysql")
        return False
    except Exception as e:
        print(f"  [ERROR] MySQL connection failed: {type(e).__name__}: {e}")
        return False


def check_db_state(host, port, user, password, database):
    """Check current DB state."""
    print("\n[4/8] Checking current database state...")
    import pymysql

    conn = pymysql.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=database,
        ssl_disabled=True,
    )

    with conn.cursor() as cur:
        # Check alembic_version
        cur.execute("SHOW TABLES LIKE 'alembic_version';")
        has_version = cur.fetchone() is not None

        if has_version:
            cur.execute("SELECT version_num FROM alembic_version;")
            row = cur.fetchone()
            version = row[0] if row else "UNKNOWN"
            print(f"  alembic_version: {version}")
        else:
            print("  [WARN] alembic_version table does not exist!")
            version = None

        # List all tables
        cur.execute("SHOW TABLES;")
        tables = [row[0] for row in cur.fetchall()]
        print(f"  Total tables: {len(tables)}")

        # Check for partial AI tables
        partial_tables = [t for t in tables if t.startswith("ai_")]
        if partial_tables:
            print(f"  Partial AI tables found: {partial_tables}")
        else:
            print("  No partial AI tables found")

        # Check row counts for AI tables
        for t in partial_tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM `{t}`;")
                count = cur.fetchone()[0]
                print(f"    {t}: {count} rows")
            except Exception as e:
                print(f"    {t}: ERROR - {e}")

    conn.close()
    return version, tables, partial_tables


def drop_partial_tables(host, port, user, password, database, partial_tables):
    """Drop partial tables from previous failed migrations."""
    print(f"\n[5/8] Dropping partial tables...")
    import pymysql

    conn = pymysql.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=database,
        ssl_disabled=True,
    )

    dropped = []
    for table in partial_tables:
        try:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS `{table}`;")
            conn.commit()
            print(f"  Dropped table: {table}")
            dropped.append(table)
        except Exception as e:
            print(f"  [ERROR] Failed to drop {table}: {e}")

    conn.close()
    print(f"  [OK] Dropped {len(dropped)} partial tables")
    return dropped


def run_alembic_migration(project_dir):
    """Run alembic upgrade head using the sync engine."""
    print("\n[6/8] Running 'alembic upgrade head'...")

    backend_dir = os.path.join(project_dir, "backend")

    # Ensure DATABASE_URL env var is available for alembic
    env = dict(os.environ)

    result = run_cmd(
        "python -m alembic upgrade head",
        cwd=backend_dir,
        env=env,
        check=False,
    )

    if result is None:
        print("  [FAIL] Migration failed. Check output above for errors.")
        return False

    print("  [OK] Migration command completed")
    return True


def verify_migration(host, port, user, password, database):
    """Verify migration completed successfully."""
    print("\n[7/8] Verifying migration...")
    import pymysql

    conn = pymysql.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=database,
        ssl_disabled=True,
    )

    with conn.cursor() as cur:
        # Check alembic_version
        cur.execute("SELECT version_num FROM alembic_version;")
        row = cur.fetchone()
        version = row[0] if row else "UNKNOWN"

        if version == "011":
            print(f"  [OK] alembic_version = {version} (expected: 011)")
        else:
            print(f"  [WARN] alembic_version = {version} (expected: 011)")

        # Count tables
        cur.execute("SHOW TABLES;")
        tables = [row[0] for row in cur.fetchall()]
        print(f"  Total tables: {len(tables)}")

        # Check for key tables
        expected_tables = [
            "users", "companies", "branches",
            "ad_campaigns", "ad_platforms", "ad_audiences",
            "social_accounts", "social_posts",
            "ai_prompts", "ai_conversations", "ai_messages",
            "followers", "follower_snapshots",
        ]
        missing = [t for t in expected_tables if t not in tables]
        if missing:
            print(f"  [WARN] Missing expected tables: {missing}")
        else:
            print(f"  [OK] All {len(expected_tables)} key tables present")

    conn.close()
    return version == "011" and len(tables) > 30


def restore_source_files(project_dir):
    """Restore database.py and env.py to original async versions."""
    print("\n[8/8] Restoring source files (async engine)...")

    backend_dir = os.path.join(project_dir, "backend")

    # Restore database.py
    db_path = os.path.join(backend_dir, "app", "database.py")
    with open(db_path, "r") as f:
        content = f.read()

    # Replace create_engine with create_async_engine
    content = content.replace(
        "from sqlalchemy import create_engine",
        "from sqlalchemy.ext.asyncio import create_async_engine"
    )
    content = content.replace(
        "engine = create_engine(DATABASE_URL, **_engine_kwargs)",
        "engine = create_async_engine(DATABASE_URL, **_engine_kwargs)"
    )

    with open(db_path, "w") as f:
        f.write(content)
    print("  [OK] database.py restored (create_async_engine)")

    # Restore env.py
    env_path = os.path.join(backend_dir, "alembic", "env.py")
    with open(env_path, "r") as f:
        content = f.read()

    content = content.replace(
        "from sqlalchemy import pool\nfrom sqlalchemy import create_engine\nfrom sqlalchemy.engine import Connection",
        "from sqlalchemy import pool\nfrom sqlalchemy.ext.asyncio import create_async_engine\nfrom sqlalchemy.engine import Connection\nimport asyncio"
    )

    content = content.replace(
        '''def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode using a sync engine (MySQL-compatible).
    """
    connectable = create_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
        echo=False,
    )

    with connectable.connect() as connection:
        do_run_migrations(connection)

    connectable.dispose()''',
        '''async def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode using an async engine.
    """
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
        echo=False,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()'''
    )

    content = content.replace(
        "    run_migrations_online()",
        "    asyncio.run(run_migrations_online())"
    )

    with open(env_path, "w") as f:
        f.write(content)
    print("  [OK] env.py restored (async engine)")


def main():
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backend_dir = os.path.join(project_dir, "backend")

    print("=" * 70)
    print("AI Marketing Platform v2.0 - Staging DB Migration")
    print("=" * 70)

    # Step 0: Check RAILWAY_TOKEN
    token = os.environ.get("RAILWAY_TOKEN", "")
    if not token:
        print("\n[ERROR] RAILWAY_TOKEN environment variable not set!")
        print("\nGet a fresh token:")
        print("  1. Go to https://railway.com/account/tokens")
        print("  2. Click 'New Token'")
        print("  3. Copy the token value")
        print("\nThen run:")
        print("  export RAILWAY_TOKEN='your-token-here'")
        print("  python scripts/run_staging_migration.py")
        sys.exit(1)

    # Step 1: Railway login
    if not railway_login(token):
        sys.exit(1)

    # Step 2: Get MySQL vars
    vars_data = get_mysql_vars(token, project_dir)

    # Try to extract connection details
    mysql_host = None
    mysql_port = None
    mysql_user = None
    mysql_password = None
    mysql_database = None

    if vars_data:
        mysql_host = vars_data.get("MYSQLHOST") or vars_data.get("MYSQL_HOST")
        mysql_port = vars_data.get("MYSQLPORT", "3306")
        mysql_user = vars_data.get("MYSQLUSER") or vars_data.get("MYSQL_USER")
        mysql_password = vars_data.get("MYSQLPASSWORD") or vars_data.get("MYSQL_PASSWORD")
        mysql_database = vars_data.get("MYSQLDATABASE") or vars_data.get("MYSQL_DATABASE")

    if not mysql_host:
        print("\n[ERROR] Could not determine MySQL connection details.")
        print("Check that the Railway project has a MySQL service.")
        sys.exit(1)

    # Use public TCP proxy if available
    public_domain = vars_data.get("MYSQL_PUBLIC_DOMAIN", "") if vars_data else ""
    public_port = vars_data.get("MYSQL_PUBLIC_PORT", "") if vars_data else ""
    if public_domain and public_port:
        print(f"  Using public TCP proxy: {public_domain}:{public_port}")
        mysql_host = public_domain
        mysql_port = public_port

    # Step 3: Test connection
    if not test_mysql_connection(mysql_host, mysql_port, mysql_user, mysql_password, mysql_database):
        print("\n[TROUBLESHOOTING]")
        print("  - Verify Railway MySQL service is running (not hibernating)")
        print("  - Check if public TCP proxy is enabled in Railway dashboard")
        print("  - Verify the token has access to the correct project/environment")
        sys.exit(1)

    # Step 4: Check DB state
    version, tables, partial = check_db_state(
        mysql_host, mysql_port, mysql_user, mysql_password, mysql_database
    )

    # Step 5: Drop partial tables
    if partial:
        drop_partial_tables(
            mysql_host, mysql_port, mysql_user, mysql_password, mysql_database, partial
        )
    else:
        print("\n[5/8] Skipping table cleanup (no partial tables found)")

    # Step 6: Run migration
    # Set DATABASE_URL for alembic
    db_url = f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}"
    os.environ["DATABASE_URL"] = db_url

    if not run_alembic_migration(project_dir):
        sys.exit(1)

    # Step 7: Verify
    success = verify_migration(
        mysql_host, mysql_port, mysql_user, mysql_password, mysql_database
    )

    # Step 8: Restore source files
    restore_source_files(project_dir)

    # Final report
    print("\n" + "=" * 70)
    if success:
        print("[SUCCESS] Migration completed successfully!")
    else:
        print("[PARTIAL] Migration ran but verification found issues.")
    print("=" * 70)
    print("\nNext steps:")
    print("  1. Commit the 004_add_indexes.py fix: git push origin main")
    print("  2. Deploy to Railway (this will use restored async engine)")
    print("  3. After deploy, test auth/register endpoints:")
    print("     curl <backend_url>/api/v2/auth/register -X POST -d '{...}'")
    print("     curl <backend_url>/api/v2/auth/login -X POST -d '{...}'")
    print("  4. Test protected endpoint:")
    print("     curl <backend_url>/api/v2/health/protected -H 'X-Company-ID: 1'")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
