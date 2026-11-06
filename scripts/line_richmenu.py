#!/usr/bin/env python3
"""
line_richmenu.py — Symcio LINE 官方帳號主選單（rich menu）產圖與部署。

WHY:
  選單是 LINE 好友進入 SaaS 漏斗（健檢 → 方案 → 試用）的第一個入口。
  以檔案定義（integrations/line/richmenu.json）+ 腳本部署，改版可回溯、不靠後台手點。

WHAT:
  render  依 richmenu.json 產生 2500x1686 PNG（3 欄 x 2 列，品牌色）
  deploy  驗證 → 建立 rich menu → 上傳圖片 → 設為所有好友預設 → 刪除同前綴舊版
          （--dry-run 只做 validate，不建立）

HOW:
  python scripts/line_richmenu.py render [--font <ttf/ttc>] [--out integrations/line/richmenu.png]
  LINE_CHANNEL_ACCESS_TOKEN=... python scripts/line_richmenu.py deploy [--dry-run]
  CI：.github/workflows/line-richmenu.yml（手動觸發）

注意：LINE API 規格依 Messaging API 文件撰寫，首次執行請先 --dry-run（呼叫官方 validate 端點）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib import request
from urllib.error import HTTPError

SPEC = Path("integrations/line/richmenu.json")
DEFAULT_OUT = Path("integrations/line/richmenu.png")
API = "https://api.line.me/v2/bot"
API_DATA = "https://api-data.line.me/v2/bot"
MAX_IMAGE_BYTES = 1_000_000  # LINE 上限 1 MB
COLS, ROWS = 3, 2
FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
]


def load_spec() -> dict:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    if len(spec["cells"]) != COLS * ROWS:
        raise SystemExit(f"[error] cells 必須剛好 {COLS * ROWS} 格")
    return spec


def cell_bounds(spec: dict) -> list[dict]:
    w, h = spec["size"]["width"], spec["size"]["height"]
    out = []
    for i in range(COLS * ROWS):
        r, c = divmod(i, COLS)
        x0, x1 = round(c * w / COLS), round((c + 1) * w / COLS)
        y0, y1 = round(r * h / ROWS), round((r + 1) * h / ROWS)
        out.append({"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})
    return out


def richmenu_body(spec: dict) -> dict:
    return {
        "size": spec["size"],
        "selected": spec["selected"],
        "name": spec["name"],
        "chatBarText": spec["chatBarText"],
        "areas": [{"bounds": b, "action": c["action"]} for b, c in zip(cell_bounds(spec), spec["cells"])],
    }


# ---------- render ----------
def render(font_path: str | None, out: Path) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    spec = load_spec()
    t = spec["theme"]
    font_file = font_path or next((f for f in FONT_CANDIDATES if Path(f).exists()), None)
    if not font_file:
        raise SystemExit("[error] 找不到中文字型；Ubuntu：sudo apt-get install -y fonts-noto-cjk，或用 --font 指定")
    title_font = ImageFont.truetype(font_file, 104)
    sub_font = ImageFont.truetype(font_file, 54)

    img = Image.new("RGB", (spec["size"]["width"], spec["size"]["height"]), t["background"])
    d = ImageDraw.Draw(img)
    gap = 14
    for b, cell in zip(cell_bounds(spec), spec["cells"]):
        box = (b["x"] + gap, b["y"] + gap, b["x"] + b["width"] - gap, b["y"] + b["height"] - gap)
        hl = cell.get("highlight")
        d.rounded_rectangle(box, radius=36, fill=t["primary"] if hl else t["accent_soft"])
        fg = "#FFFFFF" if hl else t["ink"]
        sub_fg = "#E6EEE8" if hl else t["primary"]
        cx = (box[0] + box[2]) / 2
        cy = (box[1] + box[3]) / 2
        d.text((cx, cy - 40), cell["label"], font=title_font, fill=fg, anchor="mm")
        d.text((cx, cy + 75), cell["sub"], font=sub_font, fill=sub_fg, anchor="mm")
        # 金色細線：視覺上提示可點擊
        d.line((cx - 60, cy + 140, cx + 60, cy + 140), fill=t["gold"], width=6)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG", optimize=True)
    if out.stat().st_size > MAX_IMAGE_BYTES:
        jpg = out.with_suffix(".jpg")
        img.save(jpg, "JPEG", quality=88, optimize=True)
        out.unlink()
        out = jpg
    print(f"[ok] {out} ({out.stat().st_size // 1024} KB, font={Path(font_file).name})")
    return out


# ---------- LINE API ----------
def call(method: str, url: str, token: str, body: bytes | None = None, ctype: str = "application/json") -> dict:
    req = request.Request(url, data=body, method=method,
                          headers={"Authorization": f"Bearer {token}", "Content-Type": ctype})
    try:
        with request.urlopen(req, timeout=30) as r:
            raw = r.read().decode() or "{}"
            return json.loads(raw)
    except HTTPError as e:
        raise SystemExit(f"[error] {method} {url} → {e.code}: {e.read().decode(errors='ignore')[:400]}") from e


def deploy(image: Path, dry_run: bool) -> None:
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
    if not token:
        raise SystemExit("[error] LINE_CHANNEL_ACCESS_TOKEN 未設定")
    if not image.exists():
        raise SystemExit(f"[error] 找不到 {image}，先執行 render")
    if image.stat().st_size > MAX_IMAGE_BYTES:
        raise SystemExit(f"[error] 圖片超過 1 MB：{image}")

    spec = load_spec()
    body = json.dumps(richmenu_body(spec), ensure_ascii=False).encode()
    call("POST", f"{API}/richmenu/validate", token, body)
    print("[ok] rich menu 結構通過 LINE validate")
    if dry_run:
        print("[dry-run] 未建立 / 未切換")
        return

    old = [m["richMenuId"] for m in call("GET", f"{API}/richmenu/list", token).get("richmenus", [])
           if m.get("name", "").startswith(spec["name"].rsplit("-", 1)[0])]
    rid = call("POST", f"{API}/richmenu", token, body)["richMenuId"]
    ctype = "image/png" if image.suffix == ".png" else "image/jpeg"
    call("POST", f"{API_DATA}/richmenu/{rid}/content", token, image.read_bytes(), ctype)
    call("POST", f"{API}/user/all/richmenu/{rid}", token)
    print(f"[ok] 新選單 {rid} 已設為預設")
    for oid in old:
        if oid != rid:
            call("DELETE", f"{API}/richmenu/{oid}", token)
            print(f"[ok] 刪除舊選單 {oid}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--font")
    r.add_argument("--out", type=Path, default=DEFAULT_OUT)
    dp = sub.add_parser("deploy")
    dp.add_argument("--image", type=Path, default=DEFAULT_OUT)
    dp.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.cmd == "render":
        render(args.font, args.out)
    else:
        deploy(args.image, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
