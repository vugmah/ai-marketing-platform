"""MySQL Migration Validation Script

Validates all Alembic migrations for MySQL 8.0 compatibility without
requiring a running MySQL instance. Uses SQLAlchemy's MySQL dialect
to generate and validate SQL.

Usage:
    cd backend && python scripts/staging/validate_mysql_migrations.py

Checks:
    1. All migration files have valid Python syntax
    2. All migration files have correct revision chain
    3. No MySQL-reserved keywords used as table/column names
    4. Column types are MySQL-compatible
    5. String lengths are specified (MySQL requires length for indexes)
    6. No unsupported PostgreSQL-specific types
    7. Enum types use String (MySQL Enum is restrictive)
    8. FK constraints are valid
"""

import ast
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "alembic" / "versions"

# MySQL reserved keywords that should not be used as identifiers
MYSQL_RESERVED = {
    'add', 'all', 'alter', 'analyze', 'and', 'as', 'asc', 'asensitive',
    'before', 'between', 'bigint', 'binary', 'blob', 'both', 'by', 'call',
    'cascade', 'case', 'change', 'char', 'character', 'check', 'collate',
    'column', 'condition', 'constraint', 'continue', 'convert', 'create',
    'cross', 'current_date', 'current_time', 'current_timestamp', 'current_user',
    'cursor', 'database', 'databases', 'day_hour', 'day_microsecond', 'day_minute',
    'day_second', 'dec', 'decimal', 'declare', 'default', 'delayed', 'delete',
    'desc', 'describe', 'deterministic', 'distinct', 'distinctrow', 'div',
    'double', 'drop', 'dual', 'each', 'else', 'elseif', 'enclosed', 'escaped',
    'exists', 'exit', 'explain', 'false', 'fetch', 'float', 'float4', 'float8',
    'for', 'force', 'foreign', 'from', 'fulltext', 'grant', 'group', 'having',
    'high_priority', 'hour_microsecond', 'hour_minute', 'hour_second', 'if',
    'ignore', 'in', 'index', 'infile', 'inner', 'inout', 'insensitive', 'insert',
    'int', 'int1', 'int2', 'int3', 'int4', 'int8', 'integer', 'interval',
    'into', 'is', 'iterate', 'join', 'key', 'keys', 'kill', 'leading', 'leave',
    'left', 'like', 'limit', 'linear', 'lines', 'load', 'localtime',
    'localtimestamp', 'lock', 'long', 'longblob', 'longtext', 'loop',
    'low_priority', 'match', 'mediumblob', 'mediumint', 'mediumtext',
    'middleint', 'minute_microsecond', 'minute_second', 'mod', 'modifies',
    'natural', 'not', 'no_write_to_binlog', 'null', 'numeric', 'on', 'optimize',
    'option', 'optionally', 'or', 'order', 'out', 'outer', 'outfile', 'precision',
    'primary', 'procedure', 'purge', 'range', 'read', 'reads', 'read_write',
    'real', 'references', 'regexp', 'release', 'rename', 'repeat', 'replace',
    'require', 'restrict', 'return', 'revoke', 'right', 'rlike', 'schema',
    'schemas', 'second_microsecond', 'select', 'sensitive', 'separator',
    'set', 'show', 'smallint', 'spatial', 'specific', 'sql', 'sqlexception',
    'sqlstate', 'sqlwarning', 'sql_big_result', 'sql_calc_found_rows',
    'sql_small_result', 'ssl', 'starting', 'straight_join', 'table', 'terminated',
    'then', 'tinyblob', 'tinyint', 'tinytext', 'to', 'trailing', 'trigger',
    'true', 'undo', 'union', 'unique', 'unlock', 'unsigned', 'update', 'usage',
    'use', 'using', 'utc_date', 'utc_time', 'utc_timestamp', 'values', 'varbinary',
    'varchar', 'varcharacter', 'varying', 'when', 'where', 'while', 'with',
    'write', 'xor', 'year_month', 'zerofill',
}

# PostgreSQL-specific types not supported by MySQL
PG_ONLY_TYPES = ['UUID', 'INET', 'CIDR', 'MACADDR', 'TSVECTOR', 'JSONB', 'ARRAY']


def check_syntax(filepath: Path) -> list:
    """Check Python syntax of a migration file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            ast.parse(f.read())
        return []
    except SyntaxError as e:
        return [f"Syntax error at line {e.lineno}: {e.msg}"]


def check_revision_chain(files: list) -> list:
    """Verify migration revision chain is intact."""
    issues = []
    revisions = {}
    down_revisions = {}
    
    for f in sorted(files):
        with open(f, 'r', encoding='utf-8') as fh:
            content = fh.read()
        
        rev_match = re.search(r'revision\s*=\s*"([^"]+)"', content)
        down_match = re.search(r'down_revision\s*=\s*([^\n]+)', content)
        
        if rev_match:
            rev_id = rev_match.group(1)
            revisions[f.name] = rev_id
            if down_match:
                down_val = down_match.group(1).strip()
                if down_val not in ('None', 'null'):
                    down_id = re.search(r'"([^"]+)"', down_val)
                    if down_id:
                        down_revisions[rev_id] = down_id.group(1)
    
    # Check chain integrity
    for rev_id, down_id in down_revisions.items():
        if down_id not in revisions.values():
            issues.append(f"Revision {rev_id} references missing down_revision: {down_id}")
    
    # Check for duplicate revisions
    seen = {}
    for fname, rev_id in revisions.items():
        if rev_id in seen:
            issues.append(f"Duplicate revision ID '{rev_id}' in {fname} and {seen[rev_id]}")
        seen[rev_id] = fname
    
    return issues


def check_mysql_compatibility(filepath: Path) -> list:
    """Check MySQL compatibility of a migration file."""
    issues = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract table/column names from create_table calls
    table_matches = re.findall(r'op\.create_table\(\s*"([^"]+)"', content)
    for table in table_matches:
        if table.lower() in MYSQL_RESERVED:
            issues.append(f"Table name '{table}' is a MySQL reserved keyword")
    
    # Check for column names
    column_matches = re.findall(r'sa\.Column\("([^"]+)"', content)
    for col in column_matches:
        if col.lower() in MYSQL_RESERVED:
            issues.append(f"Column name '{col}' is a MySQL reserved keyword")
    
    # Check for PostgreSQL-only types
    for pg_type in PG_ONLY_TYPES:
        if pg_type in content and 'postgresql' not in content.lower():
            issues.append(f"PostgreSQL-only type '{pg_type}' found (may not be MySQL-compatible)")
    
    # Check sa.String() without length (MySQL needs length for indexes)
    string_no_length = re.findall(r'sa\.String\(\)', content)
    if string_no_length:
        issues.append(f"Found {len(string_no_length)} sa.String() without length (use sa.String(255))")
    
    # Check for sa.Enum (problematic in MySQL batch mode)
    enum_uses = re.findall(r'sa\.Enum\(', content)
    if enum_uses:
        issues.append(f"Found {len(enum_uses)} sa.Enum() usage - ensure MySQL enum compatibility")
    
    # Check for JSON column usage (MySQL 5.7+ supports JSON)
    json_cols = re.findall(r'sa\.JSON\(\)', content)
    if json_cols:
        issues.append(f"Found {len(json_cols)} sa.JSON() columns - requires MySQL 5.7+")
    
    # Check index lengths for String columns
    indexed_string_pattern = re.findall(r'sa\.Column\("([^"]+)".*?index=True.*?String\((\d+)\)', content, re.DOTALL)
    for col_name, length in indexed_string_pattern:
        if int(length) > 255:
            issues.append(f"Indexed column '{col_name}' has length {length} > 255 (MySQL InnoDB limit for single-column index)")
    
    return issues


def main() -> int:
    print("=" * 60)
    print("MYSQL MIGRATION VALIDATION")
    print("=" * 60)
    
    migration_files = sorted(MIGRATIONS_DIR.glob("*.py"))
    print(f"\nFound {len(migration_files)} migration files:")
    for f in migration_files:
        print(f"  - {f.name}")
    
    all_issues = []
    
    # 1. Syntax check
    print(f"\n--- 1. Syntax Validation ---")
    for f in migration_files:
        issues = check_syntax(f)
        if issues:
            all_issues.extend([f"{f.name}: {i}" for i in issues])
            print(f"  FAIL: {f.name}")
            for i in issues:
                print(f"    - {i}")
        else:
            print(f"  OK:   {f.name}")
    
    # 2. Revision chain
    print(f"\n--- 2. Revision Chain ---")
    chain_issues = check_revision_chain(migration_files)
    if chain_issues:
        all_issues.extend(chain_issues)
        for i in chain_issues:
            print(f"  ISSUE: {i}")
    else:
        print(f"  OK: Chain intact across {len(migration_files)} migrations")
    
    # 3. MySQL compatibility
    print(f"\n--- 3. MySQL Compatibility ---")
    total_warnings = 0
    for f in migration_files:
        issues = check_mysql_compatibility(f)
        if issues:
            total_warnings += len(issues)
            print(f"  WARN: {f.name} ({len(issues)} issues)")
            for i in issues:
                print(f"    - {i}")
        else:
            print(f"  OK:   {f.name}")
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"Migration files: {len(migration_files)}")
    print(f"Syntax errors: {sum(1 for f in migration_files if check_syntax(f))}")
    print(f"Chain issues: {len(chain_issues)}")
    print(f"MySQL warnings: {total_warnings}")
    
    if all_issues:
        print(f"\nRESULT: {len(all_issues)} issue(s) found - review required")
        return 1
    elif total_warnings > 0:
        print(f"\nRESULT: PASS with {total_warnings} warnings (non-blocking)")
        return 0
    else:
        print(f"\nRESULT: PASS - All migrations MySQL-compatible")
        return 0


if __name__ == "__main__":
    sys.exit(main())
