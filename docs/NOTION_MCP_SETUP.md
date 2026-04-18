# Notion MCP × Claude Code CLI（路徑 B）本機設定

起床後 **3 分鐘** 完成，不需要重開機。

## WHY 走這條而不是 A 或 C

| 路徑 | 場景 | 現狀 |
|------|------|------|
| A. claude.ai 網頁 Notion Connector（OAuth）| 在網頁 Claude 對話讀 Notion | 你之前遇到 `Invalid MCP state`（瀏覽器 cookie 問題）|
| **B. Claude Code CLI + Notion MCP**（本篇）| 在 Mac 終端機 `claude` 對話直接問 Notion 問題 | 本篇搞定 |
| C. GitHub Actions `notion-sync.yml` | 每日把 Notion 同步到 repo `docs/notion-sync/` | 獨立管線，已備好 |

B 和 C 不互斥，建議都開。

---

## 前置條件

- [x] 你有 Notion Internal Integration，token 以 `ntn_` 開頭
- [x] 你已經 `Reset` 過之前對話曝光的 token，拿了新的
- [x] 本機裝了 Node.js ≥ 18（`node --version` 確認）
- [x] 本機裝了 Claude Code CLI（在 Mac 終端機能跑 `claude`）

---

## 三步驟（依序做）

### Step 1 — 跑一行 script 自動寫入設定（30 秒）

在你本機 repo 根目錄（Terminal）：

```bash
cd ~/path/to/BrandOS-Infrastructure
git pull origin main     # 拉最新 script
bash scripts/setup-notion-mcp-local.sh <你新的 ntn_ token>
```

Script 會：
- 找到 `~/.claude.json` 或 `~/.claude/settings.json`（沒有會建立）
- 備份舊檔（`.bak.<timestamp>`）
- 用 Python 安全 merge JSON（不會破壞其他 MCP server 設定）
- 同時寫入「駝峰」與「巢狀」兩種格式（向下+向上相容 Claude Code 不同版本）

### Step 2 — 在 Notion 授權你要讀的頁面（1 分鐘）

到你要讓 AI 讀的 Notion 頁面或 database：

1. 右上角 **⋯** → **連線（Connections）**
2. **加入連線** → 勾你的 integration（名稱可能是 `BrandOS Sync` 或你命名的）
3. 子頁面會自動繼承，不用每頁設

### Step 3 — 重啟 Claude Code CLI（30 秒）

**不是電腦重開機**——只是關掉當前 `claude` session 開新的：

```bash
# 在當前 Claude Code 對話裡
exit

# 再開一個新的
claude
```

---

## 驗證成功

在新 Claude Code session 裡打：

> 「列出我 Notion 可存取的頁面」

若成功：Claude 會呼叫 `mcp__notion__*` 工具並回傳頁面清單。

若失敗：見下方除錯。

---

## 除錯

### `mcp__notion__*` 工具沒出現
- 檢查 `~/.claude.json` 語法：`python3 -m json.tool ~/.claude.json`
- 確認已重啟 Claude Code（不是只 reload；要完整 exit + 重開）
- 看 Claude Code 啟動時的 log（通常在終端機直接顯示），有 MCP 載入錯誤會印出來

### `Unauthorized` 或 `401`
- Token 打錯或過期 → 回 https://www.notion.so/profile/integrations 點你的 integration → **Show** 複製新的 → 再跑 Step 1
- Token 對，但頁面沒授權 → 做 Step 2

### `npx @notionhq/notion-mcp-server` 下載失敗
- 檢查本機 Node 版本：`node --version`（需 ≥ 18）
- 檢查網路是否能到 npm registry：`curl -I https://registry.npmjs.org`
- 強制清快取重試：`npx clear-npx-cache && npx -y @notionhq/notion-mcp-server`

### 想還原
```bash
# 備份檔在 setup script 輸出最後一行
cp ~/.claude.json.bak.<timestamp> ~/.claude.json
```

---

## 安全

- ❌ **不要**把 `ntn_...` commit 進 repo（`~/.claude.json` 在 home，不在 repo，安全）
- ❌ **不要**把 token 貼到 AI 對話（包含這個 Claude Code session 的對話紀錄）
- ✅ Token 只存在於：你本機 `~/.claude.json` + GitHub Secret `NOTION_API_KEY`（給 Actions 用的是同一個 integration）

## 同個 integration 可以雙用

你的 Internal Integration token 同時被：
- 本機 Claude Code（透過 `~/.claude.json`，用於對話）
- GitHub Actions（透過 Secret `NOTION_API_KEY`，用於每日同步到 `docs/notion-sync/`）

兩邊各自獨立認證，互不影響。
