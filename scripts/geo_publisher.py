#!/usr/bin/env python3
"""
geo_publisher.py — geo_content 自動發布 agent（P3 roadmap）。

WHY:
  CLAUDE.md §9.3 P3 — GEO 內容自動發布。
  geo_content 從 'approved' 流轉到 'published' 不該手動跑 SQL：
  publisher 把這層自動化，同時在 docs/geo-content/ 留 markdown 副本當 audit trail。

WHAT:
  從 geo_content 取 status='approved' AND slug IS NOT NULL 的列，
  每筆做兩件事（同 transaction）：
  1. 寫 docs/geo-content/<slug>.md（front-matter + content）
  2. UPDATE status='published', published_at=NOW()

  RLS policy（geo_content_public_read）已是 published_at IS NOT NULL，
  所以 publisher 一旦更新，公開讀取立刻生效。

HOW:
  set SUPABASE_DB_URL=postgresql://...（pooler URL）
  python scripts/geo_publisher.py [--dry-run]

  CI 觸發：.github/workflows/geo-publisher.yml（daily cron + dispatch）
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import psycopg
except ImportError:
    print("[error] psycopg (v3) not installed. Run: pip install 'psycopg[binary]'", file=sys.stderr)
    sys.exit(1)


OUT_DIR = Path("docs/geo-content")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,253}[a-z0-9]$")


def is_valid_slug(slug: str | None) -> bool:
    return bool(slug) and bool(SLUG_RE.match(slug))


def render_markdown(row: dict) -> str:
    target_queries = row.get("target_queries") or []
    platforms = row.get("platforms") or []

    def yaml_str(v: object) -> str:
        s = str(v).replace('"', '\\"')
        return f'"{s}"'

    fm_lines = [
        "---",
        f'id: {yaml_str(row["id"])}',
        f'slug: {yaml_str(row["slug"])}',
        f'title: {yaml_str(row.get("title") or "")}',
        f'content_type: {yaml_str(row.get("content_type") or "")}',
        f'brand_id: {yaml_str(row.get("brand_id") or "")}',
        f'target_queries: [{", ".join(yaml_str(q) for q in target_queries)}]',
        f'platforms: [{", ".join(yaml_str(p) for p in platforms)}]',
        f'published_at: {yaml_str(datetime.now(timezone.utc).isoformat(timespec="seconds"))}',
        "---",
        "",
    ]
    body = (row.get("content") or "").rstrip() + "\n"
    title = row.get("title") or row["slug"]
    return "\n".join(fm_lines) + f"# {title}\n\n{body}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="不寫檔、不更新 DB，僅印 preview")
    args = parser.parse_args()

    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("[error] set SUPABASE_DB_URL (pooler URL, IPv4, port 6543)", file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, brand_id, content_type, title, content,
                       target_queries, platforms, slug
                FROM geo_content
                WHERE status = 'approved' AND slug IS NOT NULL
                ORDER BY updated_at ASC
                """
            )
            cols = [c.name for c in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        print(f"[info] {len(rows)} approved rows ready to publish")

        published_ids: list[str] = []
        skipped: list[tuple[str, str]] = []
        for row in rows:
            slug = row["slug"]
            if not is_valid_slug(slug):
                skipped.append((row["id"], f"invalid slug: {slug!r}"))
                continue
            target = OUT_DIR / f"{slug}.md"
            md = render_markdown(row)

            if args.dry_run:
                print(f"  would write {target} ({len(md)} bytes)")
                print(f"  would UPDATE id={row['id']} status='approved' → 'published'")
                continue

            target.write_text(md, encoding="utf-8")
            published_ids.append(row["id"])
            print(f"  wrote {target}")

        if skipped:
            print(f"[warn] {len(skipped)} rows skipped:")
            for rid, why in skipped:
                print(f"    {rid}: {why}")

        if not args.dry_run and published_ids:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE geo_content
                    SET status = 'published', published_at = NOW(), updated_at = NOW()
                    WHERE id = ANY(%s) AND status = 'approved'
                    """,
                    (published_ids,),
                )
                affected = cur.rowcount
            conn.commit()
            print(f"[done] published {affected} rows; markdown in {OUT_DIR}/")
        elif args.dry_run:
            print(f"[done] dry-run; would publish {len(rows) - len(skipped)} rows")
        else:
            print("[done] nothing to publish")

    return 0


if __name__ == "__main__":
    sys.exit(main())
