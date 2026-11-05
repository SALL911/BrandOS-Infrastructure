# Symcio AI 助手團隊 v1.0
## docs/ai-team/README.md | 設計依據：90 天主軸 = BrandOS SaaS 訂閱

---

## 一、WHY：設計約束

| 約束 | 來源 | 對設計的影響 |
|------|------|-------------|
| 90 天營收主軸 = BrandOS SaaS 訂閱 | 創辦人決策 | 助手只服務「流量 → 試用 → 付費 → 續約」這條線 |
| 最大人工瓶頸 = 每日內容產出 | 創辦人回饋 | 內容官排第一個上線 |
| 創辦人用錄音轉文字輸入 | 創辦人回饋 | 總監必須能吃長篇、口語、跳躍的逐字稿 |
| 完整 bot 身份 | 創辦人決策 | 每個助手獨立帳號、獨立權限、獨立審計軌跡 |
| GitHub ToS：一人僅能擁有一個免費 machine account | GitHub 條款 | GitHub 端改用「每個助手一個 GitHub App」，不開多個 machine user |
| 社群平台禁止未授權自動化發文（LinkedIn 等）| 平台條款 | 發布前保留人工一鍵確認；助手只排程到已授權工具 |
| Supabase `service_role` key 會繞過 RLS | 技術風險 | 每個助手獨立 Postgres role，只授權自己需要的表 |

---

## 二、WHAT：團隊編制（1 總監 + 3 核心）

| 代號 | 角色 | 唯一 KPI | 主要寫入位置 |
|------|------|---------|-------------|
| `director` | 總監助手：設計、檢查、分派其他助手；接收語音傾倒 | 任務一次通過率（無返工比例）| GitHub Issues、`.claude/agents/`、`agent_tasks` |
| `content-operator` | 內容官：每日 GEO / 社群 / 電子報內容 | 每日內容準時入庫且通過審核 | `geo_content`、`content/` |
| `growth-operator` | 增長官：SaaS 試用 → 付費 → 續約 | 試用轉付費率、30 天流失率 | HubSpot（via Composio）、Gmail 草稿、`leads` |
| `product-engineer` | 產品工程師：BrandOS SaaS 功能、migration、CI | 每週合併 PR 數 × CI 綠燈率 | GitHub PR、`supabase/migrations/` |

### 刻意不設的助手（兵貴精）

| 不設 | 原因 | 由誰兼任 |
|------|------|---------|
| ESG 顧問助手 | 不在 90 天營收主軸 | 需要時呼叫既有 `agents/brand-analyst.md` |
| 外聯 / BD 助手 | 與增長官職責重疊 | `growth-operator` |
| 數據分析助手 | AVI 引擎已由 cron 腳本產出 | `product-engineer` 維護腳本；`growth-operator` 讀結果 |
| QA 助手 | 檢查是總監職責 | `director` |

新增助手門檻：同一類任務每週 ≥ 5 次、且現有助手處理後一次通過率 < 70%，才由總監提案新增。

---

## 三、HOW：工具鏈與獨立帳號

### 3.1 身份矩陣

| 系統 | director | content-operator | growth-operator | product-engineer |
|------|---------|-----------------|----------------|-----------------|
| Google Workspace 信箱 | `director-bot@symcio.tw` | `content-bot@symcio.tw` | `growth-bot@symcio.tw` | `eng-bot@symcio.tw` |
| GitHub App | `symcio-director`（issues: write, pull_requests: write 僅 review）| `symcio-content`（contents: write 限 `content/**` 經 PR）| `symcio-growth`（issues: write）| `symcio-engineer`（contents / pull_requests / actions: write）|
| Notion integration | 讀全部、寫 `Inbox` / `Tasks` | 讀 brief、寫 `Content Drafts` | 讀 CRM 草稿 | 讀 `Specs` |
| Supabase role | `bot_director`：`agent_tasks` 讀/新增/改狀態；`knowledge_nodes`、`memory_contexts` 新增 | `bot_content`：`geo_content` 只能新增/修改 `draft` 列，不能改 status | `bot_growth`：漏斗表唯讀（不含 Stripe raw_event）；`leads` 只能改 status/notes | migration 走 CI，不給直連寫入 |
| HubSpot private app | — | — | `growth-bot`（contacts / deals write、不可刪除）| — |
| Composio entity | — | `content`（Buffer / Gmail 草稿）| `growth`（HubSpot / Gmail 草稿）| — |
| 對外寄信 | 不寄 | 不寄 | **只建草稿**，人工按送出 | 不寄 |

月成本估算：Google Workspace 4 席 × Business Starter ≈ US$28–40；GitHub App / Notion integration / HubSpot private app 免費。

### 3.2 祕密管理
- 資料庫權限定義在 `supabase/migrations/20261105000000_bot_roles.sql`，行為測試 `supabase/tests/bot_roles_test.sql`（CI 必跑）。全部無 DELETE。
- 登入帳號不進 repo。創辦人在 Supabase SQL Editor 執行（每個助手一次，密碼由密碼管理器產生）：
  ```sql
  CREATE ROLE director_bot LOGIN PASSWORD '<產生的密碼>' IN ROLE bot_director;
  CREATE ROLE content_bot  LOGIN PASSWORD '<產生的密碼>' IN ROLE bot_content;
  CREATE ROLE growth_bot   LOGIN PASSWORD '<產生的密碼>' IN ROLE bot_growth;
  ```
  pooler 連線字串使用者名稱為 `<帳號>.<project_ref>`，分別存成 GitHub Secrets `DIRECTOR_SUPABASE_DB_URL`、`CONTENT_SUPABASE_DB_URL`、`GROWTH_SUPABASE_DB_URL`。
- 停用助手：`ALTER ROLE content_bot NOLOGIN;`
- 所有 key 放 GitHub Secrets，命名 `<BOT>_<SYSTEM>_KEY`，例：`CONTENT_NOTION_KEY`、`GROWTH_HUBSPOT_TOKEN`
- 每把 key 只掛在使用它的 workflow 的 `env:`，不放 repo 層級共用
- 每季輪替；離職/停用助手 = 撤銷其 GitHub App 安裝 + 停用信箱

### 3.3 消滅人肉複製貼上：四條管線

```
[A 語音 → 任務]
錄音轉逐字稿 → 貼給 director → 複述確認(Y) → GitHub Issue（label: bot:*）+ agent_tasks 列
                                                     │
[B 每日內容]                                          ▼
Notion brief / news_items → content-operator → geo_content(status=draft)
  → 人工在 Notion 勾 approved → notion-sync → geo-publisher(cron) → 排程工具

[C 試用轉付費]
Typeform / 網站註冊 → leads → lead-scorer(cron) → composio-hubspot-sync
  → growth-operator 依分數產 Gmail 草稿 + HubSpot task → 人工送出

[D 產品]
Issue(bot:engineer) → product-engineer 開 PR → director review → 人工 merge → supabase-deploy
```

人工只剩四個按鈕：**語音確認 Y、內容 approved、寄信送出、PR merge**。其餘搬運由 workflow 完成。

---

## 四、技能包（邊幹活邊寫）

- 位置：`.claude/skills/<bot>-<task>/SKILL.md`，模板見 `docs/ai-team/SKILL_TEMPLATE.md`
- 觸發條件（任一成立就必須寫或更新）：
  1. 同一操作第 2 次出現
  2. 創辦人修正過一次輸出
  3. 踩到工具/API 的坑
- 流程：助手在交付 PR 中附帶技能包變更 → director 審核 → merge 後全隊可用
- 每週五 director 出「技能包週報」：新增 / 修改 / 淘汰清單

---

## 五、上線順序（14 天）

| 天 | 動作 | 驗收 |
|----|------|------|
| D1 | 開 4 個 Workspace 帳號；建 4 個 GitHub App；GitHub labels `bot:director/content/growth/engineer` | 帳號可登入、App 已安裝 |
| D2 | 上線 `director`（Claude.ai Project + Claude Code subagent）| 用一段真實語音逐字稿跑通複述確認 → 開出 Issue |
| D3–D5 | 上線 `content-operator`；建 Supabase role `bot_content` migration | 連續 3 天內容 08:00 前進 `draft` |
| D6–D7 | director 對 content-operator 做第一次「實習生考核」| 一次通過率 ≥ 70% |
| D8–D10 | 上線 `growth-operator`；HubSpot private app；Composio entity | 新 lead 24h 內有草稿 |
| D11–D14 | 上線 `product-engineer` | 第 1 個 PR 經 director review 後合併 |

---

## 六、檔案索引

| 檔案 | 用途 |
|------|------|
| `.claude/agents/director.md` | 總監助手（Claude Code subagent；本文亦可貼為 Claude.ai Project 指令）|
| `.claude/agents/content-operator.md` | 內容官 |
| `.claude/agents/growth-operator.md` | 增長官 |
| `.claude/agents/product-engineer.md` | 產品工程師 |
| `docs/ai-team/SKILL_TEMPLATE.md` | 技能包模板 |
