#!/usr/bin/env bash
# Symcio — 自動把 Notion MCP 接到本機 Claude Code CLI
# Usage:
#   bash scripts/setup-notion-mcp-local.sh <NTN_TOKEN>
# 例：
#   bash scripts/setup-notion-mcp-local.sh ntn_xxxxxxxxxxxxxxxx

set -euo pipefail

NTN_TOKEN="${1:-}"
if [[ -z "$NTN_TOKEN" ]]; then
  echo "Usage: $0 <NTN_TOKEN>"
  echo ""
  echo "取得 token：https://www.notion.so/profile/integrations"
  echo "→ 點你的 integration → Internal Integration Secret → Show → Copy"
  exit 1
fi

if [[ ! "$NTN_TOKEN" =~ ^ntn_|^secret_ ]]; then
  echo "⚠  token 前綴不是 'ntn_' 或 'secret_'，可能貼錯了。"
  echo "    現在是：${NTN_TOKEN:0:8}..."
  read -r -p "    仍要繼續嗎？ [y/N] " yn
  [[ "$yn" == "y" || "$yn" == "Y" ]] || exit 1
fi

# Claude Code 的設定檔位置（依版本不同有兩種）
CANDIDATES=(
  "$HOME/.claude.json"
  "$HOME/.claude/settings.json"
)

TARGET=""
for f in "${CANDIDATES[@]}"; do
  if [[ -f "$f" ]]; then
    TARGET="$f"
    break
  fi
done

if [[ -z "$TARGET" ]]; then
  TARGET="$HOME/.claude.json"
  echo "找不到現有設定，會建立新檔：$TARGET"
  mkdir -p "$(dirname "$TARGET")"
  echo '{}' > "$TARGET"
fi

# 備份
BACKUP="${TARGET}.bak.$(date +%s)"
cp "$TARGET" "$BACKUP"
echo "✓ 已備份現有設定 → $BACKUP"

# 用 Python 安全地 merge JSON（避免 shell 字串處理出錯）
python3 - "$TARGET" "$NTN_TOKEN" <<'PY'
import json
import sys
from pathlib import Path

target_path = Path(sys.argv[1])
token = sys.argv[2]

data = {}
text = target_path.read_text(encoding="utf-8").strip()
if text:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"✗ 現有設定檔 JSON 無效：{e}", file=sys.stderr)
        sys.exit(2)

# 舊版 Claude Code 使用 mcpServers（駝峰），新版使用 mcp.servers（巢狀）
# 兩種都寫，讓設定向下相容
mcp_servers_config = {
    "command": "npx",
    "args": ["-y", "@notionhq/notion-mcp-server"],
    "env": {
        "OPENAPI_MCP_HEADERS": json.dumps({
            "Authorization": f"Bearer {token}",
            "Notion-Version": "2022-06-28",
        }),
    },
}

# 駝峰版（多數 Claude Code CLI 版本）
data.setdefault("mcpServers", {})
data["mcpServers"]["notion"] = mcp_servers_config

# 巢狀版（未來版本）
data.setdefault("mcp", {}).setdefault("servers", {})
data["mcp"]["servers"]["notion"] = mcp_servers_config

target_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"✓ Notion MCP 已寫入 {target_path}")
PY

echo ""
echo "=================================================="
echo "✅ Notion MCP 已設定完成。下一步："
echo ""
echo "  1. 到 Notion 中你要讓 AI 讀的頁面"
echo "     右上 ⋯ → Connections → 勾你的 integration"
echo ""
echo "  2. 重啟 Claude Code CLI（關掉舊 session 開新的）："
echo "     exit"
echo "     claude"
echo ""
echo "  3. 在對話中試：「列出我 Notion 中所有可存取的頁面」"
echo "     Claude Code 會自動呼叫 mcp__notion__* 工具。"
echo ""
echo "若失敗：還原備份"
echo "     cp \"$BACKUP\" \"$TARGET\""
echo "=================================================="
