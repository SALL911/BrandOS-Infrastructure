#!/usr/bin/env python3
"""
social_publisher.py — 社群貼文自動發布。

WHY:
  Symcio 以自身品牌作為 BCI 量測的第一個案例，官方社群需要穩定節奏的發文，
  且每一則對外發言都要留下「誰核准、何時發、發到哪、結果如何」的稽核紀錄。

WHAT:
  取 social_posts 中 status IN ('approved','partial') 且 scheduled_at 到期的貼文，
  逐通路發布，結果寫入 social_post_deliveries：
    ok       發布成功（同一貼文同一通路不會再發第二次）
    skipped  該通路 secrets 未設定，或內容不符合該通路條件
             （若貼文指定的通路全部未設定，貼文維持 approved 等待，不會被消耗）
    failed   API 錯誤；下一輪重試，累計 3 次後放棄
  全部通路皆 ok/skipped → published；仍有可重試的失敗 → partial；全部放棄 → failed。

HOW:
  SUPABASE_DB_URL=postgresql://... python scripts/social_publisher.py [--dry-run] [--limit N]
  CI：.github/workflows/social-publisher.yml

  人工核准（Supabase SQL Editor）：
    UPDATE social_posts SET status='approved', approved_by='sall', approved_at=NOW() WHERE id='...';
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from social.channels import PUBLISHERS, REQUIRED_ENV, is_configured  # noqa: E402
from social.common import ChannelError, lint_copy  # noqa: E402

MAX_ATTEMPTS = 3


def plan_channels(post: dict, done: set[str], failures: dict[str, int], env: dict[str, str]):
    """回傳 (要發的通路, [(略過通路, 原因)], 已放棄的通路)。純函式，方便測試。"""
    todo, skipped, given_up = [], [], []
    for ch in post["channels"]:
        if ch in done:
            continue
        if ch not in PUBLISHERS:
            skipped.append((ch, "unknown-channel"))
        elif not is_configured(ch, env):
            skipped.append((ch, "not-configured: " + ", ".join(REQUIRED_ENV[ch])))
        elif ch == "instagram" and not post.get("image_url"):
            skipped.append((ch, "instagram-needs-image_url"))
        elif failures.get(ch, 0) >= MAX_ATTEMPTS:
            given_up.append(ch)
        else:
            todo.append(ch)
    return todo, skipped, given_up


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="只印出計畫，不呼叫任何社群 API、不寫 DB")
    ap.add_argument("--limit", type=int, default=5, help="單次最多處理幾則（預設 5）")
    args = ap.parse_args()

    db_url = os.environ.get("SUPABASE_DB_URL", "").strip()
    if not db_url:
        print("[error] SUPABASE_DB_URL is not set", file=sys.stderr)
        return 2
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("[error] psycopg (v3) not installed. Run: pip install 'psycopg[binary]'", file=sys.stderr)
        return 2

    env = dict(os.environ)
    configured = [c for c in PUBLISHERS if is_configured(c, env)]
    print(f"[info] configured channels: {configured or 'none'}")

    exit_code = 0
    with psycopg.connect(db_url, row_factory=dict_row, autocommit=True) as conn:
        posts = conn.execute(
            """
            SELECT id, title, body_short, body_medium, link_url, image_url, tags, channels, status
            FROM social_posts
            WHERE status IN ('approved', 'partial') AND scheduled_at <= NOW()
            ORDER BY scheduled_at
            LIMIT %s
            """,
            (args.limit,),
        ).fetchall()
        print(f"[info] due posts: {len(posts)}")

        for post in posts:
            pid = post["id"]
            problems = lint_copy(" ".join(filter(None, [post["title"], post["body_short"], post["body_medium"]])))
            if problems:
                # 不符品牌語氣規範的內容不發，退回人工修改
                print(f"[reject] {pid} {post['title']!r}: {problems}")
                if not args.dry_run:
                    conn.execute("UPDATE social_posts SET status='rejected' WHERE id=%s", (pid,))
                continue

            rows = conn.execute(
                "SELECT channel, status FROM social_post_deliveries WHERE post_id=%s", (pid,)
            ).fetchall()
            done = {r["channel"] for r in rows if r["status"] in ("ok", "skipped")}
            failures: dict[str, int] = {}
            for r in rows:
                if r["status"] == "failed":
                    failures[r["channel"]] = failures.get(r["channel"], 0) + 1

            todo, skipped, given_up = plan_channels(post, done, failures, env)
            print(f"[post] {pid} {post['title']!r} → publish={todo} skip={[s[0] for s in skipped]} given_up={given_up}")
            if not todo and not given_up and not any(r["status"] == "ok" for r in rows):
                # 這則貼文的通路目前全部未設定：維持 approved，等 secrets 補上後再發，
                # 不可標成 published 把內容消耗掉
                print("  [wait] no configured channel for this post; left as approved")
                continue
            if args.dry_run:
                continue

            for ch, reason in skipped:
                conn.execute(
                    "INSERT INTO social_post_deliveries (post_id, channel, status, error) VALUES (%s,%s,'skipped',%s)",
                    (pid, ch, reason[:1000]),
                )

            retryable = False
            for ch in todo:
                try:
                    ext_id, ext_url = PUBLISHERS[ch](post, env)
                    conn.execute(
                        "INSERT INTO social_post_deliveries (post_id, channel, status, external_id, external_url) "
                        "VALUES (%s,%s,'ok',%s,%s)",
                        (pid, ch, str(ext_id)[:300], ext_url[:1000] or None),
                    )
                    print(f"  [ok] {ch} {ext_url or ext_id}")
                except (ChannelError, KeyError) as e:
                    exit_code = 1
                    retryable = retryable or failures.get(ch, 0) + 1 < MAX_ATTEMPTS
                    conn.execute(
                        "INSERT INTO social_post_deliveries (post_id, channel, status, error) VALUES (%s,%s,'failed',%s)",
                        (pid, ch, f"{type(e).__name__}: {e}"[:1000]),
                    )
                    print(f"  [failed] {ch}: {type(e).__name__}: {e}", file=sys.stderr)

            ok_count = conn.execute(
                "SELECT COUNT(*) AS n FROM social_post_deliveries WHERE post_id=%s AND status='ok'", (pid,)
            ).fetchone()["n"]
            if retryable:
                status = "partial"
            elif ok_count > 0 or not (todo or given_up):
                status = "published"
            else:
                status = "failed"
            conn.execute(
                "UPDATE social_posts SET status=%s, published_at=CASE WHEN %s='published' THEN NOW() ELSE published_at END "
                "WHERE id=%s",
                (status, status, pid),
            )
            print(f"  [status] {status}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
