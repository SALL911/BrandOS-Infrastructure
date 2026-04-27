#!/usr/bin/env python3
"""
notion_to_knowledge_nodes.py — 把 docs/notion-sync/*.md 的內容 UPSERT 進 Supabase
                                knowledge_nodes（第二段：repo → DB）。

WHY:
  CLAUDE.md §9.2 規範：Notion → docs/notion-sync/ → knowledge_nodes（單向 cron）。
  第一段（Notion → docs/notion-sync/）由 .github/workflows/notion-sync.yml 處理；
  本腳本實作第二段。

WHAT:
  讀取 docs/notion-sync/*.md（不含 README.md），解析 YAML-like front-matter
  取出 notion_id / title，將 markdown body 整段塞進 knowledge_nodes.insight。
  source = 'notion:<page_id>'（穩定 ID，搭配 partial unique index UPSERT）。

HOW:
  set SUPABASE_DB_URL=postgresql://...（pooler URL，IPv4，port 6543）
  python scripts/notion_to_knowledge_nodes.py [--dry-run]

  CI 觸發：.github/workflows/notion-to-supabase.yml（push to main / docs/notion-sync）
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    print("[error] psycopg (v3) not installed. Run: pip install 'psycopg[binary]'", file=sys.stderr)
    sys.exit(1)


FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
SYNC_DIR = Path("docs/notion-sync")
DEFAULT_NODE_TYPE = "notion_page"


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    m = FRONT_MATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        fm[k.strip()] = v
    return fm, text[m.end():]


def collect_pages() -> list[dict[str, str]]:
    if not SYNC_DIR.exists():
        return []
    pages: list[dict[str, str]] = []
    for f in sorted(SYNC_DIR.glob("*.md")):
        if f.name == "README.md":
            continue
        text = f.read_text(encoding="utf-8")
        fm, body = parse_front_matter(text)
        page_id = fm.get("notion_id")
        if not page_id:
            print(f"  [skip] {f.name}: missing notion_id front-matter", file=sys.stderr)
            continue
        title = fm.get("title") or f.stem
        pages.append(
            {
                "source": f"notion:{page_id}",
                "node_type": DEFAULT_NODE_TYPE,
                "title": title[:500],
                "insight": body.strip() or "(empty)",
            }
        )
    return pages


def upsert(pages: list[dict[str, str]], dry_run: bool) -> int:
    if not pages:
        print("[info] no pages to upsert")
        return 0

    sql = """
        INSERT INTO knowledge_nodes (source, node_type, title, insight, updated_at)
        VALUES (%(source)s, %(node_type)s, %(title)s, %(insight)s, NOW())
        ON CONFLICT (source) WHERE source LIKE 'notion:%%'
        DO UPDATE SET
          title      = EXCLUDED.title,
          insight    = EXCLUDED.insight,
          node_type  = EXCLUDED.node_type,
          updated_at = NOW();
    """

    if dry_run:
        for p in pages[:10]:
            print(f"  would UPSERT source={p['source']!r}, title={p['title']!r}")
        if len(pages) > 10:
            print(f"  ...and {len(pages) - 10} more")
        return len(pages)

    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("[error] set SUPABASE_DB_URL (pooler URL, IPv4, port 6543)", file=sys.stderr)
        sys.exit(1)

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, pages)
        conn.commit()

    return len(pages)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="不寫 DB，僅印 preview")
    args = parser.parse_args()

    pages = collect_pages()
    print(f"[info] discovered {len(pages)} notion-sync pages with notion_id")

    n = upsert(pages, args.dry_run)

    verb = "would upsert" if args.dry_run else "upserted"
    print(f"[done] {verb} {n} knowledge_nodes rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
