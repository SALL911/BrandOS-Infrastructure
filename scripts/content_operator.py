#!/usr/bin/env python3
"""
content_operator.py — 內容官每日產出（.claude/agents/content-operator.md）。

WHY:
  每日內容產出是創辦人最大的人工瓶頸。本腳本每天 07:00（Asia/Taipei）自動產出
  當日內容草稿，人類只需在 PR 上修改、刪除不要的檔案、merge 即完成審核。

WHAT:
  1. 以 bot_content 身份連線（拒絕 superuser / BYPASSRLS / 非 bot_content 成員）
  2. 讀取素材：近 72 小時 news_items、AIVI 去識別彙總（不含品牌名稱）、
     公開 knowledge_nodes、近 30 天已產出標題（避免重複）
  3. 呼叫 Claude（structured output）產出：GEO 長文 ×1、LinkedIn ×1、X ×2、週一電子報段落 ×1
  4. 規則檢查：禁用詞 → 整篇丟棄；來源不在素材清單 → 標記待確認
  5. INSERT geo_content status='draft'；同時寫 content/daily/<date>/<slug>.md 供 PR 審稿

HOW:
  CONTENT_SUPABASE_DB_URL=postgresql://content_bot.<ref>:...@...:6543/postgres
  ANTHROPIC_API_KEY=...
  python scripts/content_operator.py [--date YYYY-MM-DD] [--dry-run] [--force]
  測試用：CONTENT_FIXTURE=<json 檔> 跳過 API 呼叫，直接用檔案內容當模型輸出。
  CI：.github/workflows/content-operator.yml；審核後由 content-approve.yml 轉 approved。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import psycopg
except ImportError:
    print("[error] psycopg (v3) not installed. Run: pip install 'psycopg[binary]'", file=sys.stderr)
    sys.exit(1)

TAIPEI = timezone(timedelta(hours=8))
OUT_ROOT = Path("content/daily")
MODEL = "claude-opus-5-5"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,253}[a-z0-9]$")

# 禁用詞：命中即整篇丟棄（CLAUDE.md §六、品牌使用規範）
FORBIDDEN = ["創新", "顛覆", "賦能", "授權代表", "official partner", "官方合作", "!", "！"]
# 內部資料表可作為來源（彙總數據）
INTERNAL_SOURCES = {"aivi_scores_monthly", "knowledge_nodes", "symcio.tw"}
X_MAX_WEIGHTED = 280  # X 計數：CJK 字元算 2
# 受測品牌數低於此值時不提供 AIVI 彙總（避免平均值即可回推單一客戶分數）
AIVI_MIN_BRANDS = 5

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "platform": {"type": "string", "enum": ["geo_article", "linkedin", "x", "newsletter"]},
                    "title": {"type": "string"},
                    "slug_suffix": {"type": "string", "description": "英文小寫 kebab-case，3-6 個字"},
                    "content": {"type": "string", "description": "繁體中文 Markdown 正文，不含來源段落"},
                    "target_queries": {"type": "array", "items": {"type": "string"}},
                    "sources": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"title": {"type": "string"}, "url": {"type": "string"}},
                            "required": ["title", "url"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["platform", "title", "slug_suffix", "content", "target_queries", "sources"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """你是 Symcio 內容官。Symcio 定義並經營 AI Visibility Intelligence（AVI）品類：
量化企業在 ChatGPT、Claude、Gemini、Perplexity 四個 AI 引擎中的曝光、排名與影響力。
當期營收主軸是 BrandOS SaaS 訂閱，所有內容的最終目的是讓 B2B 決策者理解問題並試用 BrandOS。

寫作規則（違反任一條，該篇會被系統丟棄）：
- 繁體中文，專業、精準、B2B 語氣；不使用感嘆號。
- 禁用詞：創新、顛覆、賦能。
- Bloomberg、SimilarWeb、SEMrush 只能作為「類比」說明品類，不得暗示授權、合作或代表關係。
- 每個數字或事實句都必須能對應到提供給你的素材；sources 只能填素材中出現的 url，
  或內部來源代號（aivi_scores_monthly / knowledge_nodes / symcio.tw）。沒有來源的句子不要寫。
- 不得出現任何客戶或受測品牌名稱；AIVI 數據只能用彙總值。
- 結構：WHY（讀者的問題）→ WHAT（Symcio 如何量化）→ HOW（讀者下一步）。

各平台規格：
- geo_article：800–1200 字，H2 小標，開頭第一段直接回答 target_queries 中的問題（讓 AI 引擎可直接引用），
  結尾 CTA：免費 AI 可見度檢測 https://symcio.tw
- linkedin：250–400 字，第一行是能單獨成立的觀點句，結尾 CTA：試用 BrandOS
- x：每則加權長度 ≤ 280（中文字算 2，約 120 個中文字），一個數據點 + 一句觀點，可附 symcio.tw
- newsletter：300–500 字，給既有訂閱者，結尾 CTA：升級方案
"""


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------- DB ----------
def assert_least_privilege(cur) -> str:
    """確認連線身份是 bot_content 成員，且不是 superuser / BYPASSRLS。"""
    cur.execute(
        """
        SELECT current_user, r.rolsuper, r.rolbypassrls,
               pg_has_role(current_user, 'bot_content', 'MEMBER')
        FROM pg_roles r WHERE r.rolname = current_user
        """
    )
    user, is_super, bypass, is_member = cur.fetchone()
    if is_super or bypass or not is_member:
        raise SystemExit(
            f"[error] 連線身份 {user!r} 不是最小權限的 bot_content 成員"
            f"（super={is_super}, bypassrls={bypass}, member={is_member}）。"
            "請使用 CONTENT_SUPABASE_DB_URL（content_bot 帳號），見 docs/ai-team/README.md §3.2"
        )
    return user


def fetch_context(cur, run_date: datetime) -> dict:
    since = run_date - timedelta(hours=72)
    cur.execute(
        """
        SELECT source, source_url, title_zh, summary_zh, bci_perspective
        FROM news_items
        WHERE COALESCE(published_at, created_at) >= %s
        ORDER BY COALESCE(published_at, created_at) DESC
        LIMIT 8
        """,
        (since,),
    )
    news = [dict(zip([c.name for c in cur.description], r)) for r in cur.fetchall()]

    # AIVI 去識別彙總：只取最新期別的家數、平均分數、等級分布，不取 brand_id / 名稱
    cur.execute(
        """
        WITH latest AS (SELECT MAX(period) AS p FROM aivi_scores_monthly),
             cur_period AS (SELECT s.* FROM aivi_scores_monthly s, latest WHERE s.period = latest.p),
             grades AS (SELECT COALESCE(grade, '?') AS grade, COUNT(*) AS n FROM cur_period GROUP BY 1)
        SELECT (SELECT to_char(p, 'YYYY-MM') FROM latest),
               (SELECT COUNT(*) FROM cur_period),
               (SELECT ROUND(AVG(composite_score), 1) FROM cur_period),
               (SELECT jsonb_object_agg(grade, n) FROM grades)
        """
    )
    row = cur.fetchone()
    aivi = None
    if row and row[1] and row[1] < AIVI_MIN_BRANDS:
        log(f"[info] AIVI 最新期別僅 {row[1]} 家（< {AIVI_MIN_BRANDS}），不提供彙總數據")
    elif row and row[1]:
        aivi = {"period": row[0], "brands": row[1], "avg_score": float(row[2] or 0), "grade_distribution": row[3]}

    cur.execute(
        """
        SELECT title, insight FROM knowledge_nodes
        WHERE is_public = TRUE ORDER BY created_at DESC LIMIT 10
        """
    )
    nodes = [{"title": t, "insight": i} for t, i in cur.fetchall()]

    cur.execute(
        "SELECT title FROM geo_content WHERE created_at >= %s ORDER BY created_at DESC LIMIT 60",
        (run_date - timedelta(days=30),),
    )
    recent_titles = [t for (t,) in cur.fetchall() if t]
    return {"news": news, "aivi": aivi, "knowledge": nodes, "recent_titles": recent_titles}


def already_generated(cur, date_str: str) -> int:
    cur.execute("SELECT COUNT(*) FROM geo_content WHERE slug LIKE %s", (f"{date_str}-%",))
    return cur.fetchone()[0]


# ---------- 生成 ----------
def build_user_prompt(ctx: dict, date_str: str, weekday: int) -> str:
    quota = "geo_article ×1、linkedin ×1、x ×2"
    if weekday == 0:
        quota += "、newsletter ×1（今天是週一）"
    return (
        f"日期：{date_str}\n今日配額：{quota}\n\n"
        "素材（JSON）：\n"
        + json.dumps(
            {
                "news_items": ctx["news"],
                "aivi_aggregate": ctx["aivi"],
                "public_knowledge": ctx["knowledge"],
                "avoid_repeating_titles": ctx["recent_titles"],
            },
            ensure_ascii=False,
            default=str,
            indent=1,
        )
        + "\n\n依配額產出內容。素材不足以支撐某篇時，寫 AVI 品類教育內容並只引用 symcio.tw。"
    )


def generate(ctx: dict, date_str: str, weekday: int) -> dict:
    fixture = os.environ.get("CONTENT_FIXTURE")
    if fixture:
        log(f"[info] CONTENT_FIXTURE={fixture}（跳過 API 呼叫）")
        return json.loads(Path(fixture).read_text(encoding="utf-8"))

    import anthropic

    client = anthropic.Anthropic()
    # 串流避免長輸出逾時；fallbacks="default" 在安全分類器誤擋時由伺服器改用建議模型重跑
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        betas=["server-side-fallback-2026-07-01"],
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(ctx, date_str, weekday)}],
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
        },
        extra_body={"fallbacks": "default"},
    ) as stream:
        msg = stream.get_final_message()

    if msg.stop_reason == "refusal":
        raise SystemExit(f"[error] 模型拒絕產出：{getattr(msg, 'stop_details', None)}")
    if msg.stop_reason == "max_tokens":
        raise SystemExit("[error] 輸出被 max_tokens 截斷")
    text = next(b.text for b in msg.content if b.type == "text")
    log(f"[info] model={msg.model} in={msg.usage.input_tokens} out={msg.usage.output_tokens}")
    return json.loads(text)


# ---------- 檢查 ----------
def weighted_len(s: str) -> int:
    return sum(2 if ord(ch) > 0x2E7F else 1 for ch in s)


def to_slug(date_str: str, platform: str, suffix: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", f"{date_str}-{platform.replace('_', '-')}-{suffix}".lower()).strip("-")[:200]
    slug, n = base, 2
    while slug in used:
        slug, n = f"{base}-{n}", n + 1
    used.add(slug)
    return slug


def review(items: list[dict], ctx: dict, date_str: str) -> tuple[list[dict], list[str]]:
    allowed_urls = {n["source_url"] for n in ctx["news"]}
    kept, report, used = [], [], set()
    for it in items:
        label = f"{it['platform']}「{it['title'][:30]}」"
        full = f"{it['title']}\n{it['content']}"
        hits = [w for w in FORBIDDEN if w.lower() in full.lower()]
        if hits:
            report.append(f"丟棄 {label}：含禁用詞 {hits}")
            continue
        warnings = []
        if not it["sources"]:
            warnings.append("無來源")
        bad = [s["url"] for s in it["sources"] if s["url"] not in allowed_urls
               and not any(k in s["url"] for k in INTERNAL_SOURCES)]
        if bad:
            warnings.append(f"來源不在素材清單：{bad}")
        if it["platform"] == "x" and weighted_len(it["content"]) > X_MAX_WEIGHTED:
            warnings.append(f"X 長度 {weighted_len(it['content'])} > {X_MAX_WEIGHTED}")
        it["slug"] = to_slug(date_str, it["platform"], it["slug_suffix"], used)
        if not SLUG_RE.match(it["slug"]):
            report.append(f"丟棄 {label}：slug 無效 {it['slug']!r}")
            continue
        it["warnings"] = warnings
        if warnings:
            report.append(f"待確認 {it['slug']}：{'；'.join(warnings)}")
        kept.append(it)
    return kept, report


def render_body(it: dict) -> str:
    src = "\n".join(f"- {s['title']}：{s['url']}" for s in it["sources"]) or "- （無）"
    return f"{it['content'].strip()}\n\n---\n資料來源：\n{src}\n"


def render_markdown(it: dict, row_id: str | None) -> str:
    q = json.dumps(it["target_queries"], ensure_ascii=False)
    fm = [
        "---",
        f"geo_content_id: {row_id or 'dry-run'}",
        f"slug: {it['slug']}",
        f"platform: {it['platform']}",
        f"title: {json.dumps(it['title'], ensure_ascii=False)}",
        f"target_queries: {q}",
        "status: draft",
        "---",
        "",
    ]
    return "\n".join(fm) + render_body(it)


# ---------- main ----------
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD（預設今天，Asia/Taipei）")
    ap.add_argument("--dry-run", action="store_true", help="不寫 DB、不寫檔，只印結果")
    ap.add_argument("--force", action="store_true", help="當日已有草稿仍重新產出")
    args = ap.parse_args()

    now = datetime.now(TAIPEI)
    run_date = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=TAIPEI) if args.date else now
    date_str = run_date.strftime("%Y-%m-%d")

    url = os.environ.get("CONTENT_SUPABASE_DB_URL")
    if not url:
        log("[error] CONTENT_SUPABASE_DB_URL 未設定（content_bot 帳號的 pooler URL）")
        return 1

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            user = assert_least_privilege(cur)
            log(f"[info] connected as {user}")
            if not args.force and (n := already_generated(cur, date_str)):
                log(f"[info] {date_str} 已有 {n} 筆草稿，略過（--force 可重跑）")
                return 0
            ctx = fetch_context(cur, run_date)
        log(f"[info] 素材：news={len(ctx['news'])} aivi={'有' if ctx['aivi'] else '無'} knowledge={len(ctx['knowledge'])}")

        result = generate(ctx, date_str, run_date.weekday())
        items, report = review(result.get("items", []), ctx, date_str)
        log(f"[info] 產出 {len(result.get('items', []))} 篇，保留 {len(items)} 篇")

        if args.dry_run:
            for it in items:
                print(render_markdown(it, None))
            print("\n".join(report) or "（無待確認事項）")
            return 0

        out_dir = OUT_ROOT / date_str
        out_dir.mkdir(parents=True, exist_ok=True)
        with conn.cursor() as cur:
            for it in items:
                cur.execute(
                    """
                    INSERT INTO geo_content (content_type, title, slug, content, target_queries, platforms, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'draft')
                    ON CONFLICT (slug) WHERE slug IS NOT NULL DO NOTHING
                    RETURNING id
                    """,
                    (it["platform"], it["title"], it["slug"], render_body(it), it["target_queries"], [it["platform"]]),
                )
                row = cur.fetchone()
                if not row:
                    report.append(f"略過 {it['slug']}：slug 已存在")
                    continue
                (out_dir / f"{it['slug']}.md").write_text(render_markdown(it, str(row[0])), encoding="utf-8")
        conn.commit()

    summary = out_dir / "REVIEW.md"
    summary.write_text(
        f"# {date_str} 每日內容審稿\n\n"
        "- 要發布：保留檔案（可直接在 PR 內修改正文）\n"
        "- 不要發布：刪除該檔案\n"
        "- merge 後 content-approve 會把保留的檔案轉為 approved，刪除的轉為 archived；"
        "geo-publisher 於 12:00 發布\n\n## 待確認\n"
        + ("\n".join(f"- {r}" for r in report) or "- 無")
        + "\n",
        encoding="utf-8",
    )
    log(f"[info] wrote {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
