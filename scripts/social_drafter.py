#!/usr/bin/env python3
"""
social_drafter.py — 由已發布的 geo_content 以 AI 起草社群貼文（status='draft'）。

WHY:
  發文節奏不該卡在「有人有空寫」。來源限定為已核准發布的 geo_content，
  AI 只做改寫與長度適配，不產生新的事實主張；草稿仍需人工核准才會對外發布。

WHAT:
  每篇 geo_content（published_at IS NOT NULL、尚未起草）產生一列 social_posts：
  body_short（≤ 200 字）、body_medium（≤ 600 字）、tags。
  違反品牌語氣規範（禁用詞、感嘆號）的草稿不寫入。

HOW:
  SUPABASE_DB_URL=... ANTHROPIC_API_KEY=... python scripts/social_drafter.py [--dry-run] [--limit N]
  模型預設 claude-opus-5-5，可用 SOCIAL_DRAFTER_MODEL 覆寫。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from social.common import lint_copy  # noqa: E402

DEFAULT_CHANNELS = ["bluesky", "threads", "facebook", "linkedin", "x"]
SITE = "https://symcio.tw"
# 文章頁網址樣板；起草時會實際請求一次，頁面不存在就退回首頁，避免社群貼文帶出失效連結
LINK_TEMPLATE = os.environ.get("SOCIAL_LINK_TEMPLATE", "").strip() or SITE + "/geo/{slug}"


def resolve_link(slug: str) -> str:
    url = LINK_TEMPLATE.format(slug=slug)
    try:
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "symcio-social-automation/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            # 線上站對不存在的文章回傳 200 + noindex（soft 404），不能只看狀態碼
            body = resp.read(200_000).decode("utf-8", "replace")
            if resp.status == 200 and 'name="robots" content="noindex"' not in body:
                return url
    except (urllib.error.URLError, TimeoutError):
        pass
    print(f"  [warn] {url} 無法開啟，連結改用首頁", file=sys.stderr)
    return SITE + "/"

SYSTEM = """你是 Symcio 的社群編輯。Symcio 是 AI Visibility Intelligence（AVI）平台，\
量化品牌在 ChatGPT / Claude / Gemini / Perplexity 的可見度，並以 BCI 品牌資本指數整合 AI 可見度、ESG 與品牌價值。

把使用者提供的文章改寫成社群貼文，讀者是台灣 B2B 企業的行銷長、品牌長與永續主管。

規範：
- 繁體中文，語氣專業、精準，先講讀者為什麼該在意，再講內容是什麼。
- 只使用原文已有的事實與數字，不新增任何原文沒有的主張、數據或客戶名稱。
- 不使用感嘆號，不使用「創新」「顛覆」「賦能」這類空洞詞彙。
- Bloomberg、SimilarWeb、SEMrush 等名稱只能作為類比，不可暗示合作或授權關係。
- Symcio、BrandOS、GEO、AVI、BCI、ESG 維持原文不翻譯。
- 內文不放網址與 hashtag，系統會另外附上。
- body_short 在 200 字元以內，適合 X / Bluesky / Threads；body_medium 在 600 字元以內，適合 LinkedIn / Facebook。
- tags 為 2 到 4 個不含 # 的標籤。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "body_short": {"type": "string"},
        "body_medium": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "body_short", "body_medium", "tags"],
    "additionalProperties": False,
}


def draft(client, model: str, title: str, content: str) -> dict | None:
    response = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        system=SYSTEM,
        # 安全分類器若婉拒請求，由伺服器端自動改用備援模型重跑
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": f"標題：{title}\n\n內文：\n{content}"}],
    )
    if response.stop_reason != "end_turn":
        print(f"  [skip] stop_reason={response.stop_reason}", file=sys.stderr)
        return None
    text = next((b.text for b in response.content if b.type == "text"), None)
    return json.loads(text) if text else None


def validate(d: dict) -> list[str]:
    problems = lint_copy(" ".join([d["title"], d["body_short"], d["body_medium"]]))
    if len(d["body_short"]) > 200:
        problems.append(f"body_short 過長（{len(d['body_short'])}）")
    if len(d["body_medium"]) > 600:
        problems.append(f"body_medium 過長（{len(d['body_medium'])}）")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="產生草稿並印出，不寫入 DB")
    ap.add_argument("--limit", type=int, default=3)
    args = ap.parse_args()

    db_url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not db_url:
        print("[error] SUPABASE_DB_URL is not set", file=sys.stderr)
        return 2
    try:
        import anthropic
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as e:
        print(f"[error] missing dependency: {e}. Run: pip install anthropic 'psycopg[binary]'", file=sys.stderr)
        return 2

    client = anthropic.Anthropic()
    model = os.environ.get("SOCIAL_DRAFTER_MODEL", "").strip() or "claude-opus-5-5"
    failed = 0

    with psycopg.connect(db_url, row_factory=dict_row, autocommit=True) as conn:
        rows = conn.execute(
            """
            SELECT g.id, g.slug, g.title, g.content
            FROM geo_content g
            WHERE g.published_at IS NOT NULL AND g.slug IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM social_posts s WHERE s.source = 'geo_content' AND s.source_id = g.id
              )
            ORDER BY g.published_at DESC
            LIMIT %s
            """,
            (args.limit,),
        ).fetchall()
        print(f"[info] geo_content to draft: {len(rows)} (model={model})")

        for row in rows:
            print(f"[draft] {row['slug']}")
            try:
                d = draft(client, model, row["title"] or row["slug"], row["content"])
            except (anthropic.APIStatusError, anthropic.APIConnectionError, json.JSONDecodeError) as e:
                failed += 1
                print(f"  [error] {type(e).__name__}: {e}", file=sys.stderr)
                continue
            if not d:
                failed += 1
                continue
            problems = validate(d)
            if problems:
                failed += 1
                print(f"  [rejected] {problems}", file=sys.stderr)
                continue
            if args.dry_run:
                print(json.dumps(d, ensure_ascii=False, indent=2))
                continue
            conn.execute(
                """
                INSERT INTO social_posts
                  (title, body_short, body_medium, link_url, tags, channels, status, source, source_id)
                VALUES (%s, %s, %s, %s, %s, %s, 'draft', 'geo_content', %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    d["title"][:300], d["body_short"], d["body_medium"],
                    resolve_link(row["slug"]), d["tags"][:4], DEFAULT_CHANNELS, row["id"],
                ),
            )
            print("  [ok] draft saved — 待人工核准")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
