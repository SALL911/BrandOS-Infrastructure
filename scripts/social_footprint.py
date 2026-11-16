#!/usr/bin/env python3
"""
social_footprint.py — Symcio 數位足跡每日快照。

WHY:
  BCI 把品牌的數位聲量視為可查證的無形資產。要「可查證」，
  就需要固定來源、固定時間、可重現的原始數字，而不是後台截圖。

WHAT:
  每個 collector 回傳 [(channel, account, metric, value)]，寫入 social_metrics
  （同日同指標以最後一次為準）。不需金鑰的來源永遠會跑；
  需要金鑰的來源在 secrets 未設定時略過，不視為失敗。

  免金鑰：Bluesky、GitHub、Zenodo（BCI 方法論 DOI 的瀏覽／下載）
  需金鑰：Facebook、Instagram、Threads、LINE、YouTube、X、LinkedIn

HOW:
  SUPABASE_DB_URL=... python scripts/social_footprint.py [--dry-run]
  CI：.github/workflows/social-footprint.yml（每日）
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from social.common import ChannelError, http_json  # noqa: E402

Metric = tuple[str, str, str, float]

GRAPH = "https://graph.facebook.com/v21.0"
DEFAULTS = {
    "BLUESKY_HANDLE": "symcioai.bsky.social",
    "GITHUB_REPOS": "SALL911/symcio",
    "ZENODO_RECORD_ID": "20419081",
    "X_USERNAME": "symciostudio",
    "LINKEDIN_ORG_ID": "105910896",
}


def _q(params: dict[str, str]) -> str:
    return urllib.parse.urlencode(params)


def collect_bluesky(env) -> list[Metric]:
    handle = env["BLUESKY_HANDLE"]
    p = http_json("GET", "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?" + _q({"actor": handle}))
    return [
        ("bluesky", handle, "followers", p.get("followersCount", 0)),
        ("bluesky", handle, "posts", p.get("postsCount", 0)),
    ]


def collect_github(env) -> list[Metric]:
    out: list[Metric] = []
    headers = {"Authorization": f"Bearer {env['GITHUB_TOKEN']}"} if env.get("GITHUB_TOKEN") else {}
    for repo in filter(None, (r.strip() for r in env["GITHUB_REPOS"].split(","))):
        r = http_json("GET", f"https://api.github.com/repos/{repo}", headers=headers)
        out += [
            ("github", repo, "stars", r.get("stargazers_count", 0)),
            ("github", repo, "forks", r.get("forks_count", 0)),
            ("github", repo, "watchers", r.get("subscribers_count", 0)),
        ]
    return out


def collect_zenodo(env) -> list[Metric]:
    rid = env["ZENODO_RECORD_ID"]
    r = http_json("GET", f"https://zenodo.org/api/records/{rid}")
    stats = r.get("stats") or {}
    account = r.get("doi") or f"zenodo.{rid}"
    return [
        ("zenodo", account, "unique_views", stats.get("unique_views", 0)),
        ("zenodo", account, "unique_downloads", stats.get("unique_downloads", 0)),
    ]


def collect_facebook(env) -> list[Metric]:
    pid = env["FB_PAGE_ID"]
    r = http_json("GET", f"{GRAPH}/{pid}?" + _q({"fields": "followers_count,fan_count", "access_token": env["FB_PAGE_ACCESS_TOKEN"]}))
    return [
        ("facebook", pid, "followers", r.get("followers_count", 0)),
        ("facebook", pid, "page_likes", r.get("fan_count", 0)),
    ]


def collect_instagram(env) -> list[Metric]:
    uid = env["IG_USER_ID"]
    r = http_json("GET", f"{GRAPH}/{uid}?" + _q({"fields": "followers_count,media_count", "access_token": env["FB_PAGE_ACCESS_TOKEN"]}))
    return [
        ("instagram", uid, "followers", r.get("followers_count", 0)),
        ("instagram", uid, "posts", r.get("media_count", 0)),
    ]


def collect_threads(env) -> list[Metric]:
    uid = env["THREADS_USER_ID"]
    r = http_json(
        "GET",
        f"https://graph.threads.net/v1.0/{uid}/threads_insights?"
        + _q({"metric": "followers_count", "access_token": env["THREADS_ACCESS_TOKEN"]}),
    )
    data = (r.get("data") or [{}])[0]
    value = (data.get("total_value") or {}).get("value", 0)
    return [("threads", uid, "followers", value)]


def collect_line(env) -> list[Metric]:
    # LINE 的好友統計隔日才會結算，取昨天（台北時間）的數字
    day = (datetime.now(timezone(timedelta(hours=8))) - timedelta(days=1)).strftime("%Y%m%d")
    r = http_json(
        "GET", f"https://api.line.me/v2/bot/insight/followers?date={day}",
        headers={"Authorization": f"Bearer {env['LINE_CHANNEL_ACCESS_TOKEN']}"},
    )
    if r.get("status") != "ready":
        raise ChannelError(f"LINE insight not ready for {day} (status={r.get('status')})")
    return [
        ("line", "official-account", "followers", r.get("followers", 0)),
        ("line", "official-account", "targeted_reaches", r.get("targetedReaches", 0)),
        ("line", "official-account", "blocks", r.get("blocks", 0)),
    ]


def collect_youtube(env) -> list[Metric]:
    cid = env["YOUTUBE_CHANNEL_ID"]
    r = http_json(
        "GET", "https://www.googleapis.com/youtube/v3/channels?"
        + _q({"part": "statistics", "id": cid, "key": env["YOUTUBE_API_KEY"]}),
    )
    items = r.get("items") or []
    if not items:
        raise ChannelError(f"YouTube channel {cid} not found")
    s = items[0]["statistics"]
    return [
        ("youtube", cid, "subscribers", float(s.get("subscriberCount", 0))),
        ("youtube", cid, "views", float(s.get("viewCount", 0))),
        ("youtube", cid, "videos", float(s.get("videoCount", 0))),
    ]


def collect_x(env) -> list[Metric]:
    user = env["X_USERNAME"]
    r = http_json(
        "GET", f"https://api.x.com/2/users/by/username/{user}?user.fields=public_metrics",
        headers={"Authorization": f"Bearer {env['X_BEARER_TOKEN']}"},
    )
    m = r["data"]["public_metrics"]
    return [
        ("x", user, "followers", m.get("followers_count", 0)),
        ("x", user, "posts", m.get("tweet_count", 0)),
    ]


def collect_linkedin(env) -> list[Metric]:
    org = env["LINKEDIN_ORG_ID"]
    urn = urllib.parse.quote(f"urn:li:organization:{org}", safe="")
    version = env.get("LINKEDIN_API_VERSION") or (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y%m")
    r = http_json(
        "GET", f"https://api.linkedin.com/rest/networkSizes/{urn}?edgeType=COMPANY_FOLLOWED_BY_MEMBER",
        headers={
            "Authorization": f"Bearer {env['LINKEDIN_ACCESS_TOKEN']}",
            "LinkedIn-Version": version,
            "X-Restli-Protocol-Version": "2.0.0",
        },
    )
    return [("linkedin", org, "followers", r.get("firstDegreeSize", 0))]


# (名稱, collector, 需要的 env)
COLLECTORS = [
    ("bluesky", collect_bluesky, ()),
    ("github", collect_github, ()),
    ("zenodo", collect_zenodo, ()),
    ("facebook", collect_facebook, ("FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN")),
    ("instagram", collect_instagram, ("IG_USER_ID", "FB_PAGE_ACCESS_TOKEN")),
    ("threads", collect_threads, ("THREADS_USER_ID", "THREADS_ACCESS_TOKEN")),
    ("line", collect_line, ("LINE_CHANNEL_ACCESS_TOKEN",)),
    ("youtube", collect_youtube, ("YOUTUBE_CHANNEL_ID", "YOUTUBE_API_KEY")),
    ("x", collect_x, ("X_BEARER_TOKEN",)),
    ("linkedin", collect_linkedin, ("LINKEDIN_ACCESS_TOKEN",)),
]


def run_collectors(env: dict[str, str]) -> tuple[list[Metric], list[str], list[str]]:
    """回傳 (metrics, 略過的來源, 失敗的來源)。單一來源失敗不影響其他來源。"""
    merged = {**DEFAULTS, **{k: v for k, v in env.items() if v.strip()}}
    metrics: list[Metric] = []
    skipped: list[str] = []
    failed: list[str] = []
    for name, fn, required in COLLECTORS:
        if not all(merged.get(k) for k in required):
            skipped.append(name)
            continue
        try:
            metrics += fn(merged)
        except (ChannelError, KeyError, TypeError, ValueError) as e:
            failed.append(name)
            print(f"[failed] {name}: {type(e).__name__}: {e}", file=sys.stderr)
    return metrics, skipped, failed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="只印出數字，不寫 DB")
    args = ap.parse_args()

    metrics, skipped, failed = run_collectors(dict(os.environ))
    for ch, account, metric, value in metrics:
        print(f"[metric] {ch:10s} {account:40s} {metric:18s} {value}")
    print(f"[info] collected={len(metrics)} skipped={skipped} failed={failed}")

    if not args.dry_run and metrics:
        db_url = os.environ.get("SUPABASE_DB_URL", "").strip()
        if not db_url:
            print("[error] SUPABASE_DB_URL is not set", file=sys.stderr)
            return 2
        import psycopg

        with psycopg.connect(db_url, autocommit=True) as conn:
            for ch, account, metric, value in metrics:
                conn.execute(
                    """
                    INSERT INTO social_metrics (channel, account, metric, value)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (captured_on, channel, account, metric)
                    DO UPDATE SET value = EXCLUDED.value, created_at = NOW()
                    """,
                    (ch, account, metric, value),
                )
        print(f"[info] wrote {len(metrics)} rows to social_metrics")

    # 全部來源都失敗才算失敗；個別失敗已印在 stderr，由 workflow summary 呈現
    return 1 if failed and not metrics else 0


if __name__ == "__main__":
    sys.exit(main())
