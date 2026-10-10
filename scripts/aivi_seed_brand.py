#!/usr/bin/env python3
"""
AIVI Seed Brand — 把 onboarding 第 2–3 步變成一條命令
------------------------------------------------------
對應 docs/AIVI-PRODUCT.md §五：
  2. INSERT brands（含 aliases、competitors、tracking_status）
  3. 產出 prompt bank → INSERT prompt_sets，locked_until = 今天 + 90 天

跑完會印出 brand_id，那個值要填進 GitHub repo variable `AIVI_BRAND_ID`，
aivi-weekly.yml 與 aivi-monthly.yml 才知道要量哪個品牌。

紅線（與 aivi_tracker.py 相同，在這裡就先擋）：
  tracking_status 為 poc / subscription 時，--consent-ref 與 --dpa-id 必填。
  沒有授權就不該在資料庫裡存在一筆「可出具名報告」的品牌。

用法：
  # 自評（Case Zero）
  python scripts/aivi_seed_brand.py --slug symcio --name Symcio \
      --domain symcio.tw --status baseline

  # 付費客戶
  python scripts/aivi_seed_brand.py --slug acme --name "艾克美" --name-en Acme \
      --domain acme.com.tw --industry technology --status poc \
      --consent-ref MSA-2026-014 --dpa-id DPA-2026-014 \
      --alias "Acme Taiwan" --alias 艾克美科技 \
      --competitor 競品甲 --competitor 競品乙

  # 只看會做什麼，不寫 DB
  python scripts/aivi_seed_brand.py --slug symcio --name Symcio --dry-run

環境變數：SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib import request
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = REPO_ROOT / "prompts"


# ---------- Supabase ----------

def _sb(method: str, path: str, body: object | None = None) -> object | None:
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        print("ERROR: 缺 SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY。", file=sys.stderr)
        raise SystemExit(2)
    req = request.Request(
        f"{url}/rest/v1/{path}",
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        method=method,
    )
    try:
        with request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8")
            return json.loads(raw) if raw else []
    except HTTPError as e:
        print(f"ERROR: Supabase {method} {path} → HTTP {e.code}: "
              f"{e.read().decode(errors='ignore')[:300]}", file=sys.stderr)
    except (URLError, json.JSONDecodeError) as e:
        print(f"ERROR: Supabase {method} {path} → {type(e).__name__}: {e}", file=sys.stderr)
    return None


def _q(value: str) -> str:
    """PostgREST 的值要避開逗號與括號，否則會被當成語法。"""
    return value.replace(",", "\\,").replace("(", "\\(").replace(")", "\\)")


# ---------- prompt bank ----------

def load_banks(slug: str, version: str, locales: list[str]) -> list[dict]:
    banks = []
    for locale in locales:
        path = PROMPTS_DIR / slug / f"{version}.{locale}.json"
        if not path.exists():
            print(f"ERROR: 找不到題庫 {path.relative_to(REPO_ROOT)}。"
                  f"先在 prompts/{slug}/ 建立 {version}.{locale}.json。", file=sys.stderr)
            raise SystemExit(2)
        data = json.loads(path.read_text(encoding="utf-8"))
        prompts = data.get("prompts") or []
        if not prompts:
            print(f"ERROR: {path.name} 沒有任何題目。", file=sys.stderr)
            raise SystemExit(2)
        ids = [p.get("id") for p in prompts]
        if len(set(ids)) != len(ids):
            print(f"ERROR: {path.name} 有重複的 prompt id。", file=sys.stderr)
            raise SystemExit(2)
        banks.append({
            "locale": locale,
            "prompts": prompts,
            "intent_mix": data.get("intent_mix"),
            "file": str(path.relative_to(REPO_ROOT)),
        })
    return banks


# ---------- main ----------

def main() -> int:
    ap = argparse.ArgumentParser(description="建立品牌與鎖版題庫（onboarding 第 2–3 步）")
    ap.add_argument("--slug", required=True, help="對應 prompts/<slug>/")
    ap.add_argument("--name", required=True, help="品牌正式名稱")
    ap.add_argument("--name-en")
    ap.add_argument("--domain")
    ap.add_argument("--industry", default="technology")
    ap.add_argument("--country", default="TW")
    ap.add_argument("--status", default="baseline",
                    choices=["prospect", "baseline", "poc", "subscription", "paused"])
    ap.add_argument("--consent-ref", help="授權書編號（poc / subscription 必填）")
    ap.add_argument("--dpa-id", help="資料處理協議編號（poc / subscription 必填）")
    ap.add_argument("--alias", action="append", default=[], help="可重複")
    ap.add_argument("--competitor", action="append", default=[], help="可重複")
    ap.add_argument("--prompt-version", default="v1")
    ap.add_argument("--locales", default="zh-TW,en")
    ap.add_argument("--lock-days", type=int, default=90, help="題庫鎖版天數，預設 90")
    ap.add_argument("--dry-run", action="store_true", help="只印計畫，不寫 DB")
    args = ap.parse_args()

    # 紅線：無授權不得建立可出報告的品牌
    if args.status in ("poc", "subscription") and not (args.consent_ref and args.dpa_id):
        print(f"ERROR: tracking_status={args.status} 需要 --consent-ref 與 --dpa-id。"
              "沒有簽約與 DPA 不得建檔。", file=sys.stderr)
        return 2

    locales = [l.strip() for l in args.locales.split(",") if l.strip()]
    banks = load_banks(args.slug, args.prompt_version, locales)
    locked_until = (date.today() + timedelta(days=args.lock_days)).isoformat()

    print(f"品牌：{args.name}（slug={args.slug}, status={args.status}）")
    print(f"  網域={args.domain or '—'} 產業={args.industry} 別名={args.alias or '—'}")
    print(f"  競品={args.competitor or '—'}")
    for b in banks:
        print(f"  題庫 [{b['locale']}] {len(b['prompts'])} 題 ← {b['file']}")
    print(f"  鎖版至 {locked_until}（{args.lock_days} 天）")

    if args.dry_run:
        print("\nDRY RUN：未寫入 Supabase。")
        return 0

    brand_row = {
        "name": args.name,
        "name_en": args.name_en,
        "domain": args.domain,
        "industry": args.industry,
        "country": args.country,
        "aliases": args.alias,
        "competitors": args.competitor,
        "tracking_status": args.status,
        "consent_ref": args.consent_ref,
        "dpa_id": args.dpa_id,
    }
    brand_row = {k: v for k, v in brand_row.items() if v is not None}

    # brands 沒有 name 的唯一索引，先查再決定 INSERT 或 PATCH，避免建出重複品牌
    existing = _sb("GET", f"brands?name=eq.{_q(args.name)}&select=id,name")
    if existing is None:
        return 1

    if existing:
        brand_id = existing[0]["id"]
        if _sb("PATCH", f"brands?id=eq.{brand_id}", brand_row) is None:
            return 1
        print(f"\nbrands：已更新既有品牌 {brand_id}")
    else:
        created = _sb("POST", "brands", [brand_row])
        if not created:
            return 1
        brand_id = created[0]["id"]
        print(f"\nbrands：已建立 {brand_id}")

    # prompt_sets 有 UNIQUE(brand_id, version, locale)，可直接 upsert
    for b in banks:
        row = {
            "brand_id": brand_id,
            "version": args.prompt_version,
            "locale": b["locale"],
            "prompts": b["prompts"],
            "intent_mix": b["intent_mix"],
            "locked_until": locked_until,
        }
        res = _sb("POST", "prompt_sets?on_conflict=brand_id,version,locale", [row])
        if res is None:
            return 1
        print(f"prompt_sets：{b['locale']} {args.prompt_version} "
              f"（{len(b['prompts'])} 題，鎖版至 {locked_until}）")

    print("\n下一步：")
    print(f"  1. 把 AIVI_BRAND_ID={brand_id} 設為 GitHub repo variable")
    print(f"  2. 設 AIVI_BRAND_SLUG={args.slug}、AIVI_BRAND_NAME={args.name}"
          + (f"、AIVI_BRAND_DOMAIN={args.domain}" if args.domain else ""))
    print(f"  3. 設 AIVI_TRACKING_STATUS={args.status}"
          + ("（並把授權編號放進 AIVI_CONSENT_REF / AIVI_DPA_ID secrets）"
             if args.status in ("poc", "subscription") else ""))
    print("  4. 手動觸發 aivi-weekly.yml，run_type=baseline")
    return 0


if __name__ == "__main__":
    sys.exit(main())
