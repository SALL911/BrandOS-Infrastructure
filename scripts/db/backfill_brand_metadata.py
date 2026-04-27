#!/usr/bin/env python3
"""
backfill_brand_metadata.py — 補 brands 表的 domain / industry 欄位。

WHY:
  線上 brands 共 74 筆，多數 domain=NULL、industry='default'。
  domain 可由 primary_email 推得（after-@），industry 需人工分類。

兩階段：
  Stage 1（自動、安全）：
    從 primary_email 抽 domain，UPDATE brands SET domain=...  WHERE domain IS NULL.
  Stage 2（半自動，需 mapping CSV）：
    讀 data/brand_industry_mapping.csv（domain,industry），
    UPDATE brands SET industry=... WHERE industry IN ('default', NULL).

用法：
  export SUPABASE_DB_URL=postgresql://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres
  python scripts/db/backfill_brand_metadata.py --stage domain
  python scripts/db/backfill_brand_metadata.py --stage industry --mapping data/brand_industry_mapping.csv
  python scripts/db/backfill_brand_metadata.py --stage all --dry-run
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    print("[error] psycopg (v3) not installed. Run: pip install 'psycopg[binary]'", file=sys.stderr)
    sys.exit(1)


def conn_from_env() -> "psycopg.Connection":
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("[error] set SUPABASE_DB_URL or DATABASE_URL", file=sys.stderr)
        sys.exit(1)
    return psycopg.connect(url)


def extract_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.split("@", 1)[1].strip().lower() or None


def stage_domain(conn, dry_run: bool) -> int:
    sql_select = """
        SELECT id, primary_email
        FROM brands
        WHERE domain IS NULL AND primary_email IS NOT NULL
    """
    with conn.cursor() as cur:
        cur.execute(sql_select)
        rows = cur.fetchall()

    updates = [
        (extract_domain(email), brand_id)
        for brand_id, email in rows
        if extract_domain(email)
    ]

    print(f"[domain] candidates: {len(rows)}, will update: {len(updates)}")

    if dry_run or not updates:
        for new_domain, brand_id in updates[:10]:
            print(f"  would UPDATE brands SET domain='{new_domain}' WHERE id='{brand_id}'")
        if len(updates) > 10:
            print(f"  ...and {len(updates) - 10} more")
        return len(updates)

    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE brands SET domain = %s WHERE id = %s AND domain IS NULL",
            updates,
        )
    conn.commit()
    print(f"[domain] updated {len(updates)} rows")
    return len(updates)


def load_mapping(path: Path) -> dict[str, str]:
    if not path.exists():
        print(f"[error] mapping CSV not found: {path}", file=sys.stderr)
        sys.exit(1)

    mapping: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            domain = (row.get("domain") or "").strip().lower()
            industry = (row.get("industry") or "").strip()
            if domain and industry:
                mapping[domain] = industry
    return mapping


def stage_industry(conn, mapping_path: Path, dry_run: bool) -> int:
    mapping = load_mapping(mapping_path)
    if not mapping:
        print(f"[industry] mapping is empty; nothing to do.")
        return 0

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, domain
            FROM brands
            WHERE domain IS NOT NULL
              AND (industry IS NULL OR industry IN ('default',''))
            """
        )
        rows = cur.fetchall()

    updates = [
        (mapping[domain], brand_id) for brand_id, domain in rows if domain in mapping
    ]
    print(
        f"[industry] candidates: {len(rows)}, "
        f"mappable: {len(updates)}, "
        f"unmapped domains: {len(rows) - len(updates)}"
    )

    if dry_run or not updates:
        for industry, brand_id in updates[:10]:
            print(f"  would UPDATE brands SET industry='{industry}' WHERE id='{brand_id}'")
        return len(updates)

    with conn.cursor() as cur:
        cur.executemany(
            """
            UPDATE brands
            SET industry = %s
            WHERE id = %s
              AND (industry IS NULL OR industry IN ('default',''))
            """,
            updates,
        )
    conn.commit()
    print(f"[industry] updated {len(updates)} rows")
    return len(updates)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["domain", "industry", "all"], default="all")
    parser.add_argument(
        "--mapping",
        type=Path,
        default=Path("data/brand_industry_mapping.csv"),
        help="CSV with domain,industry columns",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with conn_from_env() as conn:
        if args.stage in ("domain", "all"):
            stage_domain(conn, args.dry_run)
        if args.stage in ("industry", "all"):
            stage_industry(conn, args.mapping, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
