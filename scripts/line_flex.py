#!/usr/bin/env python3
"""
line_flex.py — Symcio LINE Flex Message 模板填值、驗證、推播。

WHY:
  健檢結果、試用提醒等通知改用 Flex 卡片，取代純文字；模板放 repo，可審稿、可回溯。

WHAT:
  render    填入變數，印出 message JSON（未填的 {{var}} 會報錯）
  validate  呼叫 LINE validate 端點檢查格式（不送出）
  push      推給單一好友（line_user_id）。只用於本人觸發的通知（健檢結果、試用提醒），
            不做群發行銷；群發請走 LINE 官方後台並遵守好友設定。

HOW:
  python scripts/line_flex.py render   --template avi-report --vars '{"brand":"...",...}'
  LINE_CHANNEL_ACCESS_TOKEN=... python scripts/line_flex.py validate --template avi-report --vars '...'
  LINE_CHANNEL_ACCESS_TOKEN=... python scripts/line_flex.py push --to Uxxxx --template trial-nudge --vars '...'
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError

FLEX_DIR = Path("integrations/line/flex")
API = "https://api.line.me/v2/bot"
VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def render(template: str, variables: dict) -> dict:
    raw = (FLEX_DIR / f"{template}.json").read_text(encoding="utf-8")
    msg = json.loads(raw)
    msg.pop("_comment", None)
    text = json.dumps(msg, ensure_ascii=False)
    missing = sorted(set(VAR_RE.findall(text)) - variables.keys())
    if missing:
        raise SystemExit(f"[error] 缺少變數：{missing}")
    # 以 JSON 字串跳脫後替換，避免變數內容破壞 JSON
    text = VAR_RE.sub(lambda m: json.dumps(str(variables[m.group(1)]), ensure_ascii=False)[1:-1], text)
    out = json.loads(text)
    if len(out.get("altText", "")) > 400:
        raise SystemExit("[error] altText 超過 400 字")
    return out


def call(path: str, body: dict) -> dict:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        raise SystemExit("[error] LINE_CHANNEL_ACCESS_TOKEN 未設定")
    req = request.Request(f"{API}{path}", data=json.dumps(body, ensure_ascii=False).encode(), method="POST",
                          headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or "{}")
    except HTTPError as e:
        raise SystemExit(f"[error] {path} → {e.code}: {e.read().decode(errors='ignore')[:400]}") from e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["render", "validate", "push"])
    ap.add_argument("--template", required=True)
    ap.add_argument("--vars", default="{}", help="JSON 物件")
    ap.add_argument("--to", help="push 對象 line_user_id")
    args = ap.parse_args()

    msg = render(args.template, json.loads(args.vars))
    if args.cmd == "render":
        print(json.dumps(msg, ensure_ascii=False, indent=2))
    elif args.cmd == "validate":
        call("/message/validate/push", {"messages": [msg]})
        print("[ok] 通過 LINE validate")
    else:
        if not args.to or not args.to.startswith("U"):
            raise SystemExit("[error] --to 必須是 line_user_id（U 開頭）")
        call("/message/push", {"to": args.to, "messages": [msg]})
        print(f"[ok] 已推播 {args.template} → {args.to[:6]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
