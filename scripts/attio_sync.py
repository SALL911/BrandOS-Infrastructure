#!/usr/bin/env python3
"""
attio_sync.py — Supabase（leads + members）→ Attio People 單向同步。

WHY:
  HubSpot 負責行銷自動化（電子報、表單、序列），Attio 負責關係與商機管理。
  兩套 CRM 並存時最大風險是「兩邊各改一半、真相分裂」，所以規則是：
    Supabase = 唯一真相；HubSpot、Attio 都只接收、不回寫。
  HubSpot 由既有 composio_hubspot_sync.py（leads）與 symcio.tw member-sync（members）負責；
  本腳本補上 Attio 這一路。

WHAT:
  - 取近 N 天新增 / 更新的 leads 與 members（以 email 合併，members 優先）
  - Attio assert people（以 email_addresses 比對：有則更新、無則建立，可重跑）
  - 只寫標準欄位：name、email_addresses、job_title、description（來源 / 方案 / lead score / 電子報同意）
  - 結果寫入 member_sync_log（target='attio'）
  - 個資紅線：不同步 LINE user id、不同步未留 email 的紀錄

HOW:
  SUPABASE_DB_URL=...  ATTIO_API_KEY=...
  python scripts/attio_sync.py [--days 2] [--dry-run]
  CI：.github/workflows/crm-sync.yml

注意：Attio API 依 v2 文件撰寫，首次請 --dry-run 並以 --limit 1 實跑確認欄位對應。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib import request
from urllib.error import HTTPError

ATTIO_ASSERT_PEOPLE = "https://api.attio.com/v2/objects/people/records?matching_attribute=email_addresses"


def fetch_contacts(cur, days: int) -> list[dict]:
    cur.execute(
        """
        SELECT lower(email) AS email, name, company, NULL::text AS title, source,
               NULL::text AS plan, score, NULL::boolean AS newsletter_opt_in, 'lead' AS kind
        FROM leads
        WHERE email IS NOT NULL AND email <> ''
          AND GREATEST(created_at, COALESCE(scored_at, created_at)) >= NOW() - make_interval(days => %s)
        """,
        (days,),
    )
    cols = [c.name for c in cur.description]
    merged = {r["email"]: r for r in (dict(zip(cols, row)) for row in cur.fetchall())}

    cur.execute(
        """
        SELECT lower(email) AS email, display_name AS name, company_name AS company, title,
               signup_source AS source, plan, NULL::int AS score, newsletter_opt_in, 'member' AS kind, id
        FROM members
        WHERE email IS NOT NULL AND email <> ''
          AND updated_at >= NOW() - make_interval(days => %s)
        """,
        (days,),
    )
    cols = [c.name for c in cur.description]
    for row in cur.fetchall():
        m = dict(zip(cols, row))
        lead = merged.get(m["email"], {})
        # members 優先，缺值由 lead 補
        merged[m["email"]] = {**lead, **{k: v for k, v in m.items() if v is not None}, "kind": "member"}
    return list(merged.values())


def to_attio_values(c: dict) -> dict:
    values: dict = {"email_addresses": [c["email"]]}
    if c.get("name"):
        full = c["name"].strip()
        first, _, last = full.rpartition(" ") if " " in full else (full, "", "")
        values["name"] = [{"first_name": first or full, "last_name": last, "full_name": full}]
    if c.get("title"):
        values["job_title"] = c["title"]
    desc = [f"Symcio {c['kind']}"]
    if c.get("company"):
        desc.append(f"公司：{c['company']}")
    if c.get("source"):
        desc.append(f"來源：{c['source']}")
    if c.get("plan"):
        desc.append(f"方案：{c['plan']}")
    if c.get("score") is not None:
        desc.append(f"lead score：{c['score']}")
    if c.get("newsletter_opt_in") is not None:
        desc.append(f"電子報同意：{'是' if c['newsletter_opt_in'] else '否'}")
    values["description"] = "｜".join(desc)
    return values


def attio_assert(api_key: str, values: dict) -> str:
    body = json.dumps({"data": {"values": values}}, ensure_ascii=False).encode()
    for attempt in range(3):
        req = request.Request(ATTIO_ASSERT_PEOPLE, data=body, method="PUT",
                              headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
        try:
            with request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read().decode() or "{}")
                return data.get("data", {}).get("id", {}).get("record_id", "")
        except HTTPError as e:
            if e.code == 429 and attempt < 2:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read().decode(errors='ignore')[:300]}") from e
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=2, help="同步近 N 天新增 / 更新的紀錄")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    import psycopg

    url = os.environ.get("SUPABASE_DB_URL")
    api_key = os.environ.get("ATTIO_API_KEY", "").strip()
    if not url:
        print("[error] SUPABASE_DB_URL 未設定", file=sys.stderr)
        return 1
    if not api_key and not args.dry_run:
        print("[error] ATTIO_API_KEY 未設定", file=sys.stderr)
        return 1

    with psycopg.connect(url) as conn, conn.cursor() as cur:
        contacts = fetch_contacts(cur, args.days)
        if args.limit:
            contacts = contacts[: args.limit]
        print(f"[info] {len(contacts)} 筆待同步")
        ok = failed = 0
        for c in contacts:
            values = to_attio_values(c)
            if args.dry_run:
                print(json.dumps(values, ensure_ascii=False))
                continue
            try:
                rid = attio_assert(api_key, values)
                status, ext, err = "ok", rid, None
                ok += 1
            except Exception as e:
                status, ext, err = "failed", None, str(e)[:500]
                failed += 1
            cur.execute(
                "INSERT INTO member_sync_log (email, member_id, target, status, external_id, error) "
                "VALUES (%s, %s, 'attio', %s, %s, %s)",
                (c["email"], c.get("id"), status, ext, err),
            )
        conn.commit()
    if not args.dry_run:
        print(f"[done] ok={ok} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
