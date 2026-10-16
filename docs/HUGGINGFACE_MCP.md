# Hugging Face MCP 連線與排錯

## WHY
Hugging Face 為 GEO 測試的開源模型備援（見 `docs/FREE_STACK.md`）。MCP 連線讓 Claude 直接查詢 Hub（models / datasets / Spaces / papers）並操作 `Symcio` 組織資產。

## WHAT：兩條連線路徑

| 路徑 | 認證 | 設定位置 |
|------|------|---------|
| claude.ai / Claude Code 雲端 session | OAuth（claude.ai Connectors） | claude.ai → Settings → Connectors → Hugging Face |
| 本機 Claude Code（VS Code / CLI） | Access Token（`HF_TOKEN`） | repo 根目錄 `.mcp.json` |

## HOW：本機設定
1. 於 https://huggingface.co/settings/tokens 建立 fine-grained token（最小權限：Read + Inference；需寫入 `Symcio` org 時再加 org write）。
2. `export HF_TOKEN=hf_xxx`（寫入 `~/.zshrc` 或 `.env.local`，不得進 repo）。
3. 於 repo 目錄執行 `claude`，首次會詢問是否核准 project MCP server `hf-mcp-server` → 核准。
4. `/mcp` 確認狀態為 connected。

## 排錯清單

| 症狀 | 原因 | 處置 |
|------|------|------|
| 工具突然 401 / 消失 | OAuth token 過期（雲端 connector token 約數小時效期） | claude.ai Connectors → Hugging Face → Disconnect → Connect 重新授權 |
| 本機 `/mcp` 顯示 failed | `HF_TOKEN` 未設定，header 展開為空 | `echo $HF_TOKEN` 確認後重開 `claude` |
| 可讀不可寫（建立 repo / 上傳失敗） | OAuth scope 僅 `read-repos` / `contribute-repos` | 改用含 write 權限的 token，或在 Hub 網頁操作 |
| 查不到 `Symcio` 私有資產 | token 未授權 org | token 設定 → Repositories permissions 加入 `Symcio` |
| 工具名找不到 | MCP server 仍在連線或被停用 | 重新整理 session；`/mcp` 檢查 |

## 驗證指令（Claude 內）
- `hf_whoami` → 應回傳 `sallhuang`，org `Symcio`（admin）
- `hf_fs ls hf://spaces/Symcio` → 應列出 `Symcio/README`
