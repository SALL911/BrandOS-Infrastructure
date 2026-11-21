#!/usr/bin/env python3
"""Supabase schema drift 檢查：repo migration 宣告的表，正式庫是否都存在。

WHY：2026-10 起 SUPABASE_ACCESS_TOKEN 失效，supabase-deploy 連續失敗，
aivi_runs 等表從未建立；AIVI Weekly 因此連續失敗數週才被發現。
本腳本每日由 supabase-health.yml 執行，缺表即 fail，交給 cron-failure-alert 開 issue。

做法：
  1. 掃 supabase/migrations/*.sql 的 CREATE TABLE，得到「應存在」的表
  2. 讀 PostgREST OpenAPI（GET /rest/v1/，service role）得到「實際存在」的表
  3. 差集非空 → exit 1，並印出缺的表與修復步驟

環境變數：SUPABASE_URL、SUPABASE_SERVICE_ROLE_KEY
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = REPO_ROOT / "supabase" / "migrations"

# 只抓 public schema（未指定或 public.）的表
CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?\"?([a-z_][a-z0-9_]*)\"?\s*\(",
    re.IGNORECASE,
)
DROP_RE = re.compile(
    r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:public\.)?\"?([a-z_][a-z0-9_]*)\"?",
    re.IGNORECASE,
)
COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def expected_tables(migrations_dir: Path = MIGRATIONS_DIR) -> dict[str, str]:
    """回傳 {table: 首次建立它的 migration 檔名}；依檔名順序處理 DROP。"""
    tables: dict[str, str] = {}
    for f in sorted(migrations_dir.glob("*.sql")):
        sql = COMMENT_RE.sub("", f.read_text(encoding="utf-8"))
        # 依出現位置處理 CREATE / DROP，避免同檔先建後刪判斷錯誤
        events = [(m.start(), "create", m.group(1).lower()) for m in CREATE_RE.finditer(sql)]
        events += [(m.start(), "drop", m.group(1).lower()) for m in DROP_RE.finditer(sql)]
        for _, kind, name in sorted(events):
            if kind == "create":
                tables.setdefault(name, f.name)
            else:
                tables.pop(name, None)
    return tables


def live_tables(url: str, key: str) -> set[str]:
    req = request.Request(
        f"{url.rstrip('/')}/rest/v1/",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Accept": "application/openapi+json"},
    )
    with request.urlopen(req, timeout=30) as r:
        spec = json.loads(r.read().decode("utf-8"))
    # Swagger 2.0：definitions 含所有 table/view；paths 形如 "/aivi_runs"
    names = set((spec.get("definitions") or {}).keys())
    names |= {p.strip("/") for p in (spec.get("paths") or {}) if p.count("/") == 1 and p != "/"}
    return {n for n in names if not n.startswith("rpc/")}


def main() -> int:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("SKIP: 未設定 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY。")
        return 0

    want = expected_tables()
    try:
        have = live_tables(url, key)
    except HTTPError as e:
        print(f"ERROR: 讀取 PostgREST schema 失敗 HTTP {e.code}（service role key 可能失效）。",
              file=sys.stderr)
        return 1
    except (URLError, json.JSONDecodeError) as e:
        print(f"ERROR: 讀取 PostgREST schema 失敗：{type(e).__name__}: {e}", file=sys.stderr)
        return 1

    missing = {t: m for t, m in want.items() if t not in have}
    print(f"Schema drift：migration 宣告 {len(want)} 張表，正式庫可見 {len(have)} 個 table/view。")
    if not missing:
        print("OK：所有 migration 宣告的表都已存在。")
        return 0

    print(f"ERROR: 正式庫缺少 {len(missing)} 張表（migration 未套用）：", file=sys.stderr)
    for t, m in sorted(missing.items(), key=lambda x: (x[1], x[0])):
        print(f"  - {t}  ← {m}", file=sys.stderr)
    print("修復：Actions → Supabase Deploy → Run workflow（confirm 填 deploy）。"
          "若 deploy 失敗，檢查 SUPABASE_DB_URL secret。", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
