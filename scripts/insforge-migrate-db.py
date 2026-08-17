"""
InsForge 数据迁移脚本
将 SQLite 数据库中的数据迁移到 InsForge PostgreSQL (via PostgREST)

用法:
  python scripts/insforge-migrate-db.py              # 全量迁移
  python scripts/insforge-migrate-db.py --dry-run     # 预览迁移计划
  python scripts/insforge-migrate-db.py --table inbox # 只迁移指定表
"""

import argparse
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# 添加项目根目录到 sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

# 迁移映射: SQLite 文件 → InsForge Postgres 表
MIGRATION_MAP = {
    "inbox.db": {
        "tables": ["inbox_items"],
        "target_schema": "inbox",
    },
    "review.db": {
        "tables": ["review_requests", "review_actions", "review_items"],
        "target_schema": "review",
    },
    "users.db": {
        "tables": ["users"],
        "target_schema": "auth",
    },
}

INSFORGE_TABLES = [
    "inbox_items",
    "review_requests",
    "review_actions",
    "review_items",
    "memories",
    "sessions",
    "audit_logs",
]


def _get_sqlite_databases() -> list[Path]:
    """Find all SQLite databases in data/ directory."""
    data_dir = _PROJECT_ROOT / "data"
    if not data_dir.exists():
        print(f"[WARN] data/ directory not found at {data_dir}")
        return []
    return sorted(data_dir.glob("*.db"))


def _get_table_schema(db_path: Path, table: str) -> list[dict]:
    """Get schema info for a table."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [{"name": row["name"], "type": row["type"]} for row in cursor.fetchall()]
    conn.close()
    return columns


def _get_row_count(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    conn.close()
    return count


def _get_all_rows(db_path: Path, table: str) -> list[dict]:
    """Read all rows from a SQLite table as dicts."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table}")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def _convert_value(value: Any) -> Any:
    """Convert SQLite value to JSON-serializable form."""
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, (datetime,)):
        return value.isoformat()
    return value


def dry_run():
    """Preview what would be migrated."""
    dbs = _get_sqlite_databases()
    if not dbs:
        print("No SQLite databases found in data/")
        return

    print(f"{'='*60}")
    print(f"  InsForge DB Migration — Dry Run")
    print(f"{'='*60}\n")

    total_rows = 0
    for db_path in dbs:
        db_name = db_path.name
        print(f"📁 {db_name} ({db_path.stat().st_size / 1024:.1f} KB)")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        for table in tables:
            count = _get_row_count(db_path, table)
            target = MIGRATION_MAP.get(db_name, {}).get("target_schema", "public")
            print(f"  ├─ {table}: {count} rows → {target}.{table}")
            total_rows += count
        print()

    print(f"{'='*60}")
    print(f"  Total: {len(dbs)} databases, {total_rows} rows to migrate")
    print(f"{'='*60}")


def migrate_table(
    db_path: Path,
    table: str,
    pgrst_url: str,
    jwt_token: str,
    batch_size: int = 100,
):
    """Migrate a single table from SQLite to PostgREST."""
    import httpx

    rows = _get_all_rows(db_path, table)
    total = len(rows)
    if total == 0:
        print(f"    ⏭  {table}: empty, skipping")
        return {"table": table, "total": 0, "imported": 0, "errors": 0}

    print(f"    ⏳ {table}: migrating {total} rows...", end="", flush=True)

    headers = {
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    if jwt_token:
        headers["Authorization"] = f"Bearer {jwt_token}"

    imported = 0
    errors = 0
    for i in range(0, total, batch_size):
        batch = rows[i : i + batch_size]
        payload = []
        for row in batch:
            cleaned = {}
            for k, v in row.items():
                cleaned[k] = _convert_value(v)
            payload.append(cleaned)

        try:
            resp = httpx.post(
                f"{pgrst_url.rstrip('/')}/{table}",
                headers=headers,
                json=payload if len(payload) > 1 else payload[0],
                timeout=30,
            )
            if resp.status_code in (200, 201, 204):
                imported += len(payload)
            else:
                print(f"\n    ❌ batch {i//batch_size}: HTTP {resp.status_code} {resp.text[:200]}")
                errors += len(payload)
        except Exception as e:
            print(f"\n    ❌ batch {i//batch_size}: {e}")
            errors += len(payload)

    status = "✅" if errors == 0 else "⚠️"
    print(f"\r    {status} {table}: {imported}/{total} imported ({errors} errors)")

    return {"table": table, "total": total, "imported": imported, "errors": errors}


def run_migration(
    pgrst_url: str,
    jwt_token: str,
    table_filter: Optional[str] = None,
):
    """Run the full migration."""
    import httpx

    dbs = _get_sqlite_databases()
    if not dbs:
        print("No SQLite databases found in data/")
        return

    print(f"{'='*60}")
    print(f"  InsForge DB Migration — Running")
    print(f"  Target: {pgrst_url}")
    print(f"{'='*60}\n")

    # Step 1: Verify PostgREST is reachable
    try:
        health = httpx.get(pgrst_url.rstrip("/") + "/", timeout=10)
        print(f"  PostgREST: {'✅' if health.is_success else '❌'} (HTTP {health.status_code})")
    except Exception as e:
        print(f"  PostgREST: ❌ {e}")
        if not confirm("  PostgREST not reachable. Continue anyway?"):
            return
    print()

    total_stats = []

    for db_path in dbs:
        db_name = db_path.name
        print(f"📁 {db_name}")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        for table in tables:
            if table_filter and table != table_filter:
                continue
            if table not in INSFORGE_TABLES:
                print(f"    ⏭  {table}: not in migration map, skipping")
                continue

            stats = migrate_table(db_path, table, pgrst_url, jwt_token)
            total_stats.append(stats)

    print(f"\n{'='*60}")
    print(f"  Migration Complete")
    print(f"{'='*60}")
    total_rows = sum(s["total"] for s in total_stats)
    imported_rows = sum(s["imported"] for s in total_stats)
    error_rows = sum(s["errors"] for s in total_stats)
    print(f"  Total tables: {len(total_stats)}")
    print(f"  Total rows:   {total_rows}")
    print(f"  Imported:     {imported_rows}")
    print(f"  Errors:       {error_rows}")
    print(f"  Status:       {'✅ All good' if error_rows == 0 else '⚠️  Some errors'}")

    # Generate report
    report = {
        "timestamp": datetime.now().isoformat(),
        "target": pgrst_url,
        "tables": total_stats,
        "summary": {
            "total_tables": len(total_stats),
            "total_rows": total_rows,
            "imported_rows": imported_rows,
            "error_rows": error_rows,
        },
    }
    report_path = _PROJECT_ROOT / "data" / "insforge-migration-report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n  Report saved to: {report_path}")


def confirm(msg: str) -> bool:
    """Ask for confirmation."""
    resp = input(f"{msg} [y/N] ").strip().lower()
    return resp in ("y", "yes")


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite data to InsForge PostgreSQL")
    parser.add_argument("--dry-run", action="store_true", help="Preview migration plan")
    parser.add_argument("--table", type=str, help="Migrate only this table")
    parser.add_argument(
        "--pgrst-url",
        type=str,
        default=os.getenv("INSFORGE_POSTGREST_URL", "http://localhost:5434"),
        help="PostgREST base URL",
    )
    parser.add_argument(
        "--jwt-token",
        type=str,
        default=os.getenv("INSFORGE_JWT_TOKEN", ""),
        help="JWT token for PostgREST auth",
    )
    args = parser.parse_args()

    if args.dry_run:
        dry_run()
        return

    print(f"\n🚀 InsForge DB Migration Tool\n")
    print(f"  This will migrate SQLite data from data/*.db to InsForge PostgreSQL.")
    print(f"  Make sure InsForge services are running before proceeding.\n")

    if not confirm("  Proceed with migration?"):
        print("Cancelled.")
        return

    run_migration(args.pgrst_url, args.jwt_token, args.table_filter=args.table)


if __name__ == "__main__":
    main()
