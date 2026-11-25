#!/usr/bin/env python3
"""
content_approve.py — 每日內容 PR merge 後，把審稿結果寫回 geo_content。

WHY:
  審稿 = merge PR，不再手動跑 SQL 或在多個工具間複製貼上。
  bot_content 不能改 status（migration 20261105000000），所以 approved 這一步
  只能由人類 merge 觸發、以管理連線執行。

WHAT（針對指定日期 <date>）:
  - content/daily/<date>/*.md 仍存在的檔案 → 以檔案正文覆蓋 content / title，status 'draft' → 'approved'
  - 當日 slug 以 <date>- 開頭、但檔案已被刪除的 draft → 'archived'
  - 只動 status='draft' 的列；已 approved / published 的不碰（可重跑）

HOW:
  SUPABASE_DB_URL=... python scripts/content_approve.py --date YYYY-MM-DD [--dry-run]
  CI：.github/workflows/content-approve.yml（content-daily PR merge 時觸發）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

try:
    import psycopg
except ImportError:
    print("[error] psycopg (v3) not installed. Run: pip install 'psycopg[binary]'", file=sys.stderr)
    sys.exit(1)

ROOT = Path("content/daily")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse(path: Path) -> tuple[dict, str]:
    """極簡 front-matter 解析（content_operator.py 產生的固定格式）。"""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n\n?(.*)$", text, re.S)
    if not m:
        raise ValueError(f"{path}: 缺少 front-matter")
    meta = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip()
    if meta.get("title", "").startswith('"'):
        meta["title"] = json.loads(meta["title"])
    return meta, m.group(2).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not DATE_RE.match(args.date):
        print(f"[error] invalid --date {args.date!r}", file=sys.stderr)
        return 1

    kept: dict[str, tuple[dict, str]] = {}
    day_dir = ROOT / args.date
    for f in sorted(day_dir.glob("*.md")) if day_dir.exists() else []:
        if f.name == "REVIEW.md":
            continue
        meta, body = parse(f)
        slug = meta.get("slug", "")
        if not slug.startswith(f"{args.date}-") or slug != f.stem:
            print(f"[error] {f}: slug {slug!r} 與檔名或日期不符", file=sys.stderr)
            return 1
        kept[slug] = (meta, body)

    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("[error] SUPABASE_DB_URL 未設定", file=sys.stderr)
        return 1

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT slug FROM geo_content WHERE status = 'draft' AND slug LIKE %s",
            (f"{args.date}-%",),
        )
        drafts = {s for (s,) in cur.fetchall()}
        approve = sorted(drafts & kept.keys())
        archive = sorted(drafts - kept.keys())
        orphan = sorted(kept.keys() - drafts)

        for slug in approve:
            meta, body = kept[slug]
            cur.execute(
                """
                UPDATE geo_content
                SET content = %s, title = %s, status = 'approved', updated_at = NOW()
                WHERE slug = %s AND status = 'draft'
                """,
                (body, meta.get("title"), slug),
            )
        if archive:
            cur.execute(
                "UPDATE geo_content SET status = 'archived', updated_at = NOW() "
                "WHERE status = 'draft' AND slug = ANY(%s)",
                (archive,),
            )
        if args.dry_run:
            conn.rollback()
        else:
            conn.commit()

    print(f"approved ({len(approve)}): {', '.join(approve) or '-'}")
    print(f"archived ({len(archive)}): {', '.join(archive) or '-'}")
    if orphan:
        print(f"[warn] 檔案存在但 DB 無對應 draft（已核准或不存在）: {', '.join(orphan)}")
    if args.dry_run:
        print("[dry-run] rolled back")
    return 0


if __name__ == "__main__":
    sys.exit(main())
