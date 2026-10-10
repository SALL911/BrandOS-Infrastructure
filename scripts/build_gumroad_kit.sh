#!/usr/bin/env bash
# 打包 Gumroad Starter Kit：注入升級連結、排除秘密與建置產物、驗證後輸出 zip + README.md。
#
# 用法：scripts/build_gumroad_kit.sh
#       UPGRADE_URL=https://buy.stripe.com/xxx scripts/build_gumroad_kit.sh   # README 內嵌升級連結
#   未設 UPGRADE_URL 時，README 改為引導買家使用 Gumroad 收據信內的升級連結（zip 不需因連結變更重打包）。
# 輸出：dist/gumroad/nextjs-claude-hubspot-starter-v<version>.zip、dist/gumroad/README.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="${KIT_DIR:-$ROOT/private/gumroad-starter-kit}"
OUT="$ROOT/dist/gumroad"
UPGRADE_URL="${UPGRADE_URL:-}"
if [ -n "$UPGRADE_URL" ]; then
  case "$UPGRADE_URL" in https://*) ;; *) echo "UPGRADE_URL must start with https://" >&2; exit 1 ;; esac
  UPGRADE_CTA="👉 **[以 \$260 差額升級 VIP 專人建置 / Upgrade for \$260](${UPGRADE_URL})**"
else
  UPGRADE_CTA="👉 **升級連結附在你的 Gumroad 購買收據信中**（The upgrade link is in your Gumroad receipt email）。"
fi

[ -f "$SRC/package.json" ] || { echo "kit source not found: $SRC" >&2; exit 1; }
VERSION="$(node -p "require('$SRC/package.json').version")"
NAME="nextjs-claude-hubspot-starter-v$VERSION"
STAGE="$(mktemp -d)/$NAME"

mkdir -p "$STAGE" "$OUT"
tar -C "$SRC" \
  --exclude=node_modules --exclude=.next --exclude='*.tsbuildinfo' --exclude=next-env.d.ts \
  --exclude=.env --exclude=.env.local --exclude='.env.*.local' \
  -cf - . | tar -C "$STAGE" -xf -

export UPGRADE_CTA
grep -rl '{{UPGRADE_CTA}}' "$STAGE" | while read -r f; do
  node -e 'const fs=require("fs");const f=process.argv[1];fs.writeFileSync(f,fs.readFileSync(f,"utf8").split("{{UPGRADE_CTA}}").join(process.env.UPGRADE_CTA))' "$f"
done
if grep -rq '{{UPGRADE_' "$STAGE"; then echo "placeholder left in package" >&2; exit 1; fi
# 防止真實金鑰外洩：只允許 .env.example 內的占位值
if grep -rEq 'sk-ant-api03-[A-Za-z0-9_-]{40,}|pat-na1-[0-9a-f]{8}-[0-9a-f]{4}|sk_live_' "$STAGE"; then
  echo "possible real secret found in package — aborting" >&2; exit 1
fi

if [ "${SKIP_VERIFY:-0}" != "1" ]; then
  (cd "$STAGE" && npm ci --no-audit --no-fund --loglevel=error && npx tsc --noEmit \
    && NEXT_TELEMETRY_DISABLED=1 npx next build >/dev/null && rm -rf node_modules .next next-env.d.ts *.tsbuildinfo)
fi

rm -f "$OUT/$NAME.zip"
(cd "$(dirname "$STAGE")" && zip -qr "$OUT/$NAME.zip" "$NAME")
cp "$STAGE/README.md" "$OUT/README.md"
echo "$OUT/$NAME.zip"
echo "$OUT/README.md"
