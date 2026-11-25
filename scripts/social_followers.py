#!/usr/bin/env python3
"""
social_followers.py — LINE 官方帳號 / Facebook 粉專 / Instagram 粉絲數每日快照。

WHY:
  粉絲數是 SaaS 漏斗頂端指標；各平台後台各看各的，無法和 leads / 試用轉換對照。
  每日寫入 social_follower_snapshots，v_social_follower_daily 提供日變化。

WHAT（未設定憑證的平台自動略過，不讓整體失敗）:
  line       GET /v2/bot/insight/followers?date=<昨日 yyyyMMdd>  → followers / targetedReaches / blocks
             （LINE 統計有延遲，取前一日；status != ready 時略過）
  facebook   GET /{page_id}?fields=followers_count,fan_count
  instagram  GET /{ig_user_id}?fields=followers_count,media_count

HOW:
  SUPABASE_DB_URL=...                          （寫入快照）
  LINE_CHANNEL_ACCESS_TOKEN=...  LINE_ACCOUNT=@symcio
  META_PAGE_ACCESS_TOKEN=...  META_PAGE_ID=...  META_IG_USER_ID=...  [META_GRAPH_VERSION=v21.0]
  python scripts/social_followers.py [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from urllib import parse, request
from urllib.error import HTTPError

TAIPEI = timezone(timedelta(hours=8))


def get_json(url: str, token: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or "{}")
    except HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='ignore')[:300]}") from e


def fetch_line(day: datetime) -> list[dict]:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        return []
    d = day.strftime("%Y%m%d")
    data = get_json(f"https://api.line.me/v2/bot/insight/followers?date={d}", token)
    if data.get("status") != "ready":
        print(f"[skip] line: insight status={data.get('status')}（LINE 統計尚未產生）")
        return []
    return [{
        "platform": "line",
        "account": os.environ.get("LINE_ACCOUNT", "line-oa"),
        "snapshot_date": day.date(),
        "followers": data.get("followers"),
        "extra": {"targetedReaches": data.get("targetedReaches"), "blocks": data.get("blocks")},
    }]


def fetch_meta(day: datetime) -> list[dict]:
    token = os.environ.get("META_PAGE_ACCESS_TOKEN", "").strip()
    if not token:
        return []
    ver = os.environ.get("META_GRAPH_VERSION", "v21.0")
    out = []
    page_id = os.environ.get("META_PAGE_ID", "").strip()
    if page_id:
        q = parse.urlencode({"fields": "followers_count,fan_count,name", "access_token": token})
        p = get_json(f"https://graph.facebook.com/{ver}/{page_id}?{q}")
        out.append({"platform": "facebook", "account": page_id, "snapshot_date": day.date(),
                    "followers": p.get("followers_count"),
                    "extra": {"fan_count": p.get("fan_count"), "name": p.get("name")}})
    ig_id = os.environ.get("META_IG_USER_ID", "").strip()
    if ig_id:
        q = parse.urlencode({"fields": "followers_count,media_count,username", "access_token": token})
        g = get_json(f"https://graph.facebook.com/{ver}/{ig_id}?{q}")
        out.append({"platform": "instagram", "account": ig_id, "snapshot_date": day.date(),
                    "followers": g.get("followers_count"),
                    "extra": {"media_count": g.get("media_count"), "username": g.get("username")}})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    today = datetime.now(TAIPEI)
    rows, errors = [], []
    for name, fn, day in (("line", fetch_line, today - timedelta(days=1)), ("meta", fetch_meta, today)):
        try:
            got = fn(day)
            if not got:
                print(f"[skip] {name}: 無資料（未設定憑證或統計未就緒）")
            rows += got
        except Exception as e:  # 單一平台失敗不影響其他平台
            errors.append(f"{name}: {e}")

    for r in rows:
        print(f"{r['platform']:<10} {r['account']:<20} {r['snapshot_date']} followers={r['followers']}")
    for e in errors:
        print(f"[error] {e}", file=sys.stderr)

    if rows and not args.dry_run:
        import psycopg

        url = os.environ.get("SUPABASE_DB_URL")
        if not url:
            print("[error] SUPABASE_DB_URL 未設定", file=sys.stderr)
            return 1
        with psycopg.connect(url) as conn, conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    """
                    INSERT INTO social_follower_snapshots (platform, account, snapshot_date, followers, extra)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (platform, account, snapshot_date)
                    DO UPDATE SET followers = EXCLUDED.followers, extra = EXCLUDED.extra
                    """,
                    (r["platform"], r["account"], r["snapshot_date"], r["followers"], json.dumps(r["extra"])),
                )
            conn.commit()
        print(f"[ok] 寫入 {len(rows)} 筆快照")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
