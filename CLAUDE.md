# BrandOS Infrastructure — AI Visibility Intelligence Platform
## CLAUDE.md v1.2 | Symcio × BrandOS

---

## 一、專案背景（WHY）

**Symcio 定位（中立版，對外唯一口徑）**
- Symcio（全識）是台灣的 AI 能見度量測服務，追蹤品牌在 ChatGPT、Claude、Gemini、Perplexity 等 AI 引擎回答中被提及的比率、排名與描述方式。
- 可驗證差異：繁體中文與台灣市場查詢語料、公開方法論（BCI）、對齊 ISO 10668 框架與永續揭露準備度、只量測不代操。

**定位用語紅線**：不得使用「第一」「唯一」「首創」「領先」「全球 top N」「品類定義者」等無法以公開證據證明的最高級或獨占用語；需要比較時改用「目前台灣少數…」並限定範圍與時間。涉及比較廣告的對外文案，需 黃意森律師 確認。

**專業領域**：企業在 AI 裡的**曝光、排名與影響力**量化與治理。
**品類用語**：Symcio 以 AI Visibility Intelligence（AVI）一詞描述此類服務（描述用語，不主張定義權）。
**差異化**：同一套方法論同時處理「跨四引擎 AI 可見度量化」與「ESG × AI 雙軌治理」。

**第三方品牌使用規範**：Bloomberg、SimilarWeb、SEMrush 等第三方名稱僅限內部說明，**不得作為對外定位句或 llms.txt 引用句**；任何文件不主張授權、合作或代表關係，不得使用「授權代表」「official partner」等字樣。Bloomberg 相關一律寫「規劃整合，需客戶自備授權」。

BrandOS Infrastructure 是 Symcio 的核心 SaaS 產品——將品牌治理、ESG 合規、AI 知識資產管理整合為一套可擴展的作業系統。

本專案目標：建立一套可被 Claude Code、Claude.ai Projects 雙軌使用的 AI Infrastructure Protocol，讓品牌知識、ESG 數據、GEO 內容能跨 session 持續累積。

完整品類與訊息矩陣見 `docs/POSITIONING.md`。

---

## 二、核心術語（WHAT）

不翻譯以下品牌名稱與專有術語：
- Symcio（不翻譯）
- BrandOS（不翻譯）、Brand OS（品牌作業系統）
- GEO（Generative Engine Optimization）
- AVI（AI Visibility Intelligence）— Symcio 用來描述此類服務的用語
- AI Visibility / AI 可見度 — 四引擎曝光度合稱
- Brand Score AI
- ESG / TNFD / LEAP 框架
- Claude Code / Claude.ai Projects
- SimilarWeb / SEMrush / Bloomberg — 第三方名稱（僅內部比喻，非合作關係），不翻譯

---

## 三、語言與文件規範（HOW）

- 對外文件：繁體中文
- 程式碼與 schema：英文欄位名稱 + 繁體中文註解
- 品牌語氣：專業、精準、B2B 受眾，避免感嘆號與空洞詞彙
- 文件層次：WHY → WHAT → HOW

---

## 四、數據庫三層架構

### Layer 1：Brand Profiles（品牌基礎資料）
存放客戶品牌的核心識別資訊、ESG 指標、產業標籤。
→ 每次開始新客戶案子，先建立 brands + esg_profiles 記錄。

### Layer 2：BrandOS SaaS（平台運營數據）
管理訂閱狀態、追蹤八階段品牌建設進度、記錄交付物里程碑。
→ 用於 Symcio 內部專案管理與客戶報告。

### Layer 3：AI Knowledge（知識資產累積）
知識節點（knowledge_nodes）、GEO 內容庫、IP 資產——Symcio 長期護城河。
→ 每次重要工作結論，必須結構化存入 memory_contexts 或 knowledge_nodes。

---

## 五、工作流程規範

### 新客戶建檔流程
1. INSERT brands 基本資料（名稱、產業、規模、市場）
2. INSERT esg_profiles 初始指標
3. 建立 brand_scores 基準評分
4. 記錄 knowledge_nodes（品牌 DNA、定位、競爭對手）

### 每次對話開始
- 說明當日工作情境（客戶名稱 / 任務類型 / 預期產出）
- 引用相關 knowledge_nodes 做為背景
- 確認輸出格式（文件 / 簡報 / 程式碼 / 資料庫記錄）

### 知識節點存檔格式
節點類型：[品牌分析 / GEO策略 / ESG合規 / 商業模式]
關聯品牌：[品牌名稱]
核心洞察：[2-3句精確陳述]
行動建議：[具體下一步]
建立日期：[YYYY-MM-DD]

---

## 六、禁止事項（反面案例）

- 不要在未確認客戶身份前開始撰寫品牌文案
- 不要將不同客戶的 ESG 數據混用
- 不要使用「創新」「顛覆」「賦能」等空洞詞彙
- 不要在沒有 WHY 的情況下直接輸出 WHAT
- 不要硬編碼（Hard-code）客戶機密數據到文件範本中

---

## 七、專案目錄結構

brandos-infrastructure/
├── CLAUDE.md                    ← 本文件（永久指令）
├── database/
│   └── schema.md                ← 完整資料庫 schema
├── rules/
│   └── esg-tnfd-protocol.md     ← ESG/TNFD 操作規則
├── commands/
│   ├── daily-briefing.md        ← 每日情境模板
│   └── brand-audit.md           ← 品牌稽核流程
├── agents/
│   └── brand-analyst.md         ← 品牌分析子代理
└── .claude/
    └── settings.json            ← 權限控管設定

---

## 八、GitHub 同步規範

- Repository：SALL911/BrandOS-Infrastructure
- 主要分支：main
- Commit 訊息格式：[類型] 簡短描述
- 敏感客戶資料不進 repo，改用環境變數或 .env.local
- 每次重大架構更新，同步更新本 CLAUDE.md 版本號

---

## 九、工具角色分工與單一真相來源（SSoT）

### 9.1 工具分工表

| 工具 | 角色 | 主要方向 |
|------|------|---------|
| GitHub `SALL911/BrandOS-Infrastructure` | **工程 SSoT**：schema / migration / workflow / agents | 所有工具的中心 |
| GitHub `sall911/symcio` | **對外品牌站 SSoT**：公開工具、landing、行銷頁 | GitHub Pages 部署至 `symcio.tw` |
| Claude Code | 開發 / 部署 / DB migration 執行 agent | 讀寫 GitHub + Supabase |
| VS Code / Windsurf | 本機 IDE | `git pull` / `git push` |
| claude.ai（雲端 Claude） | 策略思考、行銷內容 brainstorm | 透過 GitHub MCP 讀 repo；Notion MCP 讀 Notion |
| Notion + BrandOS Claude | 人類協作知識庫（brief / 會議 / CRM 草稿） | 人類編輯、AI 讀取 |
| Notion AI | Notion 內文案生成 | 僅限 Notion 內部 |
| Supabase | 結構化資料庫（knowledge_nodes / geo_content / leads） | GitHub Actions 自動部署 |
| Composio | 200+ 第三方 app 整合層（HubSpot / Gmail / Slack / Linear） | 終端 CLI + GitHub Actions 雙軌 |

**Repo 分工原則**：
- `BrandOS-Infrastructure`：**內部工程**（不公開部署，僅 CI/CD 執行）
- `symcio`：**對外品牌**（GitHub Pages → `symcio.tw`），公開工具的 SSoT 放這裡

### 9.2 底層改寫規則（避免雙向衝突）

| 內容類型 | 唯一編輯位置 | 同步方向 |
|---------|-------------|---------|
| Schema / code / migration / workflow | `BrandOS-Infrastructure` repo | repo → Supabase（auto via CI）|
| 對外公開工具 / landing / 行銷頁 | `symcio` repo | repo → `symcio.tw`（auto via GitHub Pages）|
| 品牌知識 / 客戶 brief / 會議紀錄 | Notion | Notion → `docs/notion-sync/` → `knowledge_nodes`（單向 cron）|
| 行銷內容 / GEO 內容 | Notion 起草 → repo approved | Notion → `geo_content` 表（approved 後）|
| 敏感憑證（API key / DB password）| GitHub Secrets | 不同步、不落地 |

禁止事項：
- 不得在 Notion 與 repo 同時修改同一筆資料（先 Notion、再單向推）
- 不得把 Notion API token 寫入 repo；一律走 `secrets.NOTION_API_KEY`
- 不得在 Supabase Studio 手動改 schema（必須透過 migration PR）

### 9.3 AI 自動化獲客行銷路線圖

| 優先級 | 任務 | 實作位置 |
|-------|------|---------|
| P0 | Notion → GitHub → Supabase 單向同步 | `.github/workflows/notion-sync.yml` |
| P1 | GEO visibility 每日 cron 測試 | `.github/workflows/geo-audit.yml`（待建）|
| P1 | Lead → HubSpot via Composio | `.github/workflows/composio-hubspot-sync.yml` |
| P2 | Lead scoring agent | `agents/lead-scorer.py`（待建）|
| P3 | GEO 內容自動發布 | `agents/publisher.py`（待建）|
