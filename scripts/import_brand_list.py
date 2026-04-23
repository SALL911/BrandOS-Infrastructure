#!/usr/bin/env python3
"""
彈性 CSV → Supabase leads + brands 匯入工具。

WHY
    歷史名單（Excel / Google Sheets 匯出的 CSV）要灌進 BrandOS，
    同時標 segment + priority，讓 geo-audit-queue 能優先掃描他們。
    不同名單欄位格式不同 → script 支援 `--col-*` 參數彈性 mapping。

PREREQS
    zero-dep：純 Python 3.10+ stdlib。不用 pandas、不用 openpyxl。
    CSV 必須是 UTF-8（Excel 匯出請選「CSV UTF-8 (逗號分隔)」；
    Google Sheets 匯出原本就 UTF-8）。

使用範例
    # 1. 先 dry-run 看看解析結果（不寫 DB）
    python scripts/import_brand_list.py data/startup-lists/verity-2026.csv \\
        --col-brand '公司名稱' \\
        --col-email 'Email' \\
        --col-domain '網站' \\
        --col-industry '產業' \\
        --col-phone '電話' \\
        --col-contact '聯絡人' \\
        --segment startup-meta-2026 \\
        --priority 10 \\
        --dry-run

    # 2. 確認解析 ok → 真的寫入
    python scripts/import_brand_list.py data/startup-lists/verity-2026.csv \\
        --col-brand '公司名稱' \\
        --col-email 'Email' \\
        ...

環境變數
    SUPABASE_URL                必填
    SUPABASE_SERVICE_ROLE_KEY   必填

設計決策
    - 有 email 的記錄才寫（沒 email 無法 re-engage，浪費空間）
    - 同 email 在 CSV 裡多筆只取第一筆（email 去重）
    - 同品牌名 brands 表已存在則 UPDATE 補 segment / priority，不覆寫原有欄位
    - 所有寫入包在 try/except，單筆失敗不擋批次
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any
from urllib import parse, request
from urllib.error import HTTPError, URLError


SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------- HTTP ----------

def _http(url: str, *, method: str = "GET", headers: dict[str, str] | None = None,
          body: Any = None, timeout: int = 30) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return {"ok": True, "status": r.status, "json": json.loads(raw) if raw else None}
    except HTTPError as e:
        return {"ok": False, "status": e.code, "text": e.read().decode(errors="ignore")[:400]}
    except URLError as e:
        return {"ok": False, "status": 0, "text": f"URL error: {e.reason}"}


def sb_headers() -> dict[str, str]:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ---------- 正規化 ----------

def norm_email(raw: str) -> str | None:
    s = (raw or "").strip().lower()
    if not s or not EMAIL_RE.match(s):
        return None
    return s


def norm_domain(raw: str) -> str | None:
    s = (raw or "").strip().lower()
    if not s:
        return None
    # 去掉 http(s):// 與路徑
    s = re.sub(r"^https?://", "", s)
    s = s.split("/")[0]
    if not s or "." not in s:
        return None
    return s[:500]


def norm_text(raw: str, maxlen: int = 255) -> str:
    return (raw or "").strip()[:maxlen]


# ---------- Supabase ----------

def find_brand_by_name(name: str) -> dict | None:
    r = _http(
        f"{SUPABASE_URL}/rest/v1/brands?name=eq.{parse.quote(name)}&select=id,segment_tags&limit=1",
        headers=sb_headers(),
    )
    if not r["ok"]:
        return None
    data = r.get("json") or []
    return data[0] if data else None


def insert_lead(row: dict) -> tuple[bool, str]:
    r = _http(
        f"{SUPABASE_URL}/rest/v1/leads",
        method="POST",
        headers=sb_headers(),
        body=[row],
    )
    if r["ok"]:
        return True, ""
    return False, f"HTTP {r['status']}: {r.get('text','')[:200]}"


def upsert_brand(new_row: dict, existing: dict | None, segment: str) -> tuple[str, str]:
    """回傳 (action, error_msg)。action ∈ {'inserted', 'updated', 'skipped'}"""
    if existing:
        # 合併 segment_tags：保留原有 + 加新的，不重複
        old_tags = existing.get("segment_tags") or []
        if not isinstance(old_tags, list):
            old_tags = []
        if segment not in old_tags:
            old_tags.append(segment)
        patch = {
            "segment_tags": old_tags,
            "priority": new_row.get("priority", 0),   # 直接套新 priority（匯入意圖就是拉優先序）
            "source_list": new_row.get("source_list"),
            "imported_at": new_row.get("imported_at"),
        }
        if new_row.get("primary_email") and not existing.get("primary_email"):
            patch["primary_email"] = new_row["primary_email"]
        r = _http(
            f"{SUPABASE_URL}/rest/v1/brands?id=eq.{existing['id']}",
            method="PATCH",
            headers=sb_headers(),
            body=patch,
        )
        if r["ok"]:
            return "updated", ""
        return "skipped", f"HTTP {r['status']}: {r.get('text','')[:200]}"
    # 新增
    r = _http(
        f"{SUPABASE_URL}/rest/v1/brands",
        method="POST",
        headers=sb_headers(),
        body=[new_row],
    )
    if r["ok"]:
        return "inserted", ""
    return "skipped", f"HTTP {r['status']}: {r.get('text','')[:200]}"


# ---------- Main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="CSV → Supabase leads + brands 匯入")
    ap.add_argument("csv_path", help="CSV file path（UTF-8）")
    ap.add_argument("--col-brand", required=True, help="品牌/公司名稱欄位名")
    ap.add_argument("--col-email", required=True,
                    help="Email 欄位名（可 comma-separated 多欄 fallback，例：'Work Email,Email'）")
    ap.add_argument("--col-domain", default=None, help="網域欄位名（選）")
    ap.add_argument("--col-industry", default=None, help="產業欄位名（選）")
    ap.add_argument("--col-contact", default=None, help="聯絡人全名欄位名（與 --col-contact-first/last 二擇一）")
    ap.add_argument("--col-contact-first", default=None, help="名（first name）欄位名")
    ap.add_argument("--col-contact-last", default=None, help="姓（last name）欄位名")
    ap.add_argument("--col-phone", default=None, help="電話欄位名（選，可用 fallback 串接：'Work Phone,Phone'）")
    ap.add_argument("--col-notes", default=None, help="備註欄位名（選，會附加到 leads.notes）")
    ap.add_argument("--segment", required=True, help="segment 標籤（例：startup-meta-2026）")
    ap.add_argument("--priority", type=int, default=10, help="priority 0–32767，高=先掃。預設 10")
    ap.add_argument("--market", default="Taiwan", help="brands.market 預設值")
    ap.add_argument("--dry-run", action="store_true", help="只解析不寫 DB")
    args = ap.parse_args()

    if not args.dry_run:
        if not SUPABASE_URL or not SUPABASE_KEY:
            print("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 必填（或加 --dry-run）",
                  file=sys.stderr)
            return 2

    imported_at = datetime.now(timezone.utc).isoformat()

    with open(args.csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("ERROR: CSV 沒有 header row", file=sys.stderr)
            return 2
        print(f"==> Headers found: {reader.fieldnames}")
        # 支援 --col-email 'Work Email,Email' fallback 串接
        email_cols = [c.strip() for c in args.col_email.split(",")]
        required_single = [args.col_brand] + email_cols[:1]  # brand + 首個 email col 必存在
        for col in required_single:
            if col not in reader.fieldnames:
                print(f"ERROR: 必要欄位 '{col}' 不在 CSV 裡。可用的欄位：{reader.fieldnames}",
                      file=sys.stderr)
                return 2

        seen_emails: set[str] = set()
        stats = {"rows": 0, "no_email": 0, "dup_email": 0, "invalid_email": 0,
                 "leads_inserted": 0, "brands_inserted": 0, "brands_updated": 0,
                 "errors": 0}
        for raw in reader:
            stats["rows"] += 1
            brand_name = norm_text(raw.get(args.col_brand, ""))
            # 按 fallback 順序試每個 email 欄位（例：先 Work Email，再 Email）
            email = None
            for col_name in email_cols:
                candidate = norm_email(raw.get(col_name, ""))
                if candidate:
                    email = candidate
                    break
            if not brand_name:
                continue
            if not email:
                any_raw = any((raw.get(c, "") or "").strip() for c in email_cols)
                stats["no_email" if not any_raw else "invalid_email"] += 1
                continue
            if email in seen_emails:
                stats["dup_email"] += 1
                continue
            seen_emails.add(email)

            domain = norm_domain(raw.get(args.col_domain, "")) if args.col_domain else None
            industry = norm_text(raw.get(args.col_industry, ""), 100) if args.col_industry else ""
            # 聯絡人：優先用 last+first 組合（Asian convention 姓先名後），
            # 退回 single-column --col-contact
            if args.col_contact_last or args.col_contact_first:
                last = norm_text(raw.get(args.col_contact_last, ""), 50) if args.col_contact_last else ""
                first = norm_text(raw.get(args.col_contact_first, ""), 50) if args.col_contact_first else ""
                contact = " ".join(filter(None, [last, first]))[:100]
            else:
                contact = norm_text(raw.get(args.col_contact, ""), 100) if args.col_contact else ""

            # 電話：col 可以是 'Work Phone,Phone' comma-separated fallback
            phone = ""
            if args.col_phone:
                for col_name in [c.strip() for c in args.col_phone.split(",")]:
                    v = norm_text(raw.get(col_name, ""), 50)
                    if v:
                        phone = v
                        break
            notes_extra = norm_text(raw.get(args.col_notes, ""), 500) if args.col_notes else ""

            lead_row = {
                "name": contact or brand_name,
                "company": brand_name,
                "email": email,
                "source": args.segment,
                "status": "new",
                "notes": "; ".join(filter(None, [
                    f"phone={phone}" if phone else "",
                    f"industry={industry}" if industry else "",
                    f"domain={domain}" if domain else "",
                    f"list={args.segment}",
                    notes_extra,
                ])),
            }
            brand_row = {
                "name": brand_name,
                "domain": domain,
                "industry": industry or "default",
                "market": args.market,
                "status": "prospect",
                "primary_email": email,
                "segment_tags": [args.segment],
                "priority": args.priority,
                "source_list": args.segment,
                "imported_at": imported_at,
            }

            if args.dry_run:
                print(f"  DRY: {brand_name[:30]:30s} | {email:40s} | "
                      f"dom={domain or '-'} | ind={industry or '-'} | pri={args.priority}")
                continue

            ok, err = insert_lead(lead_row)
            if ok:
                stats["leads_inserted"] += 1
            else:
                stats["errors"] += 1
                print(f"  ! lead 失敗 {email}: {err}")
                continue  # 不寫 brand，避免孤兒

            existing = find_brand_by_name(brand_name)
            action, err = upsert_brand(brand_row, existing, args.segment)
            if action == "inserted":
                stats["brands_inserted"] += 1
            elif action == "updated":
                stats["brands_updated"] += 1
            else:
                stats["errors"] += 1
                print(f"  ! brand 失敗 {brand_name}: {err}")

        print("\n── Summary ──")
        for k, v in stats.items():
            print(f"  {k:22s} {v}")

    print(f"\n✓ Done. Segment='{args.segment}' priority={args.priority}")
    if args.dry_run:
        print("  （dry-run；移除 --dry-run 才會實際寫入）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
