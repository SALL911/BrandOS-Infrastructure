# Symcio BrandOS — 完整產品地圖

> **定位**：Symcio（全識）是台灣的 AI 能見度量測服務，追蹤品牌在 ChatGPT、Claude、Gemini、Perplexity 等 AI 引擎回答中被提及的比率、排名與描述方式。
> **護城河**：BCI（Brand Capital Index）公式 — 把金融資本、AI 可見度、品牌參與度三個原本不相關的市場統一成單一時序指標。公式公開、權重閉源。

---

## 一、產品組成（六大層，由上而下）

```
┌─────────────────────────────────────────────────────────────────┐
│  L1  公開官網（symcio.tw）                                        │
│       Next.js 14 App Router + Tailwind + Chart.js                │
│       首頁 / 診斷 / 方案 / 知識庫 / 工具 / 關於                     │
├─────────────────────────────────────────────────────────────────┤
│  L2  會員系統 + Dashboard                                         │
│       Supabase Auth（Email + Google OAuth）                       │
│       BCI 歷史儲存（audit_history）+ 配額                         │
├─────────────────────────────────────────────────────────────────┤
│  L3  交易 / 付款                                                  │
│       Stripe Checkout（$299 Audit / Pro / Enterprise）             │
│       付款 → repository_dispatch → geo-audit.yml → Resend email   │
├─────────────────────────────────────────────────────────────────┤
│  L4  AI 可見度引擎（GEO Audit）                                   │
│       scripts/geo_audit.py — 4 engines × N prompts                │
│       → visibility_results + PDF report → email                   │
├─────────────────────────────────────────────────────────────────┤
│  L5  BCI 引擎 + Calibration                                       │
│       scripts/bci_engine.py（Python）+ lib/scoring.ts（TS）       │
│       scripts/bci_calibrate.py — 權重 grid search                 │
│       scripts/collect_fixtures.py — InterBrand / Kantar 合併       │
├─────────────────────────────────────────────────────────────────┤
│  L6  行銷獲客（內容 + 冷信 + 電子報）                              │
│       content/medium/ · content/linkedin/ · content/cold-outreach/ │
│       scripts/prepare_content.sh — 發布準備                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、檔案樹（部署相關）

```
BrandOS-Infrastructure/
├── web/landing/                          ← 🚀 Vercel 部署這一層
│   ├── app/
│   │   ├── page.tsx                      首頁（4 板塊 + BCI + 6 模組）
│   │   ├── layout.tsx                    root layout（GA4 + Organization Schema）
│   │   ├── globals.css                   全域樣式
│   │   ├── (auth)/
│   │   │   ├── layout.tsx                登入群專用 layout
│   │   │   ├── login/page.tsx
│   │   │   ├── signup/page.tsx
│   │   │   ├── forgot-password/page.tsx
│   │   │   └── reset-password/page.tsx
│   │   ├── auth/
│   │   │   ├── callback/route.ts         OAuth code exchange
│   │   │   └── logout/route.ts
│   │   ├── dashboard/
│   │   │   ├── layout.tsx                session-protected layout
│   │   │   ├── page.tsx                  Overview
│   │   │   ├── history/page.tsx          BCI 歷史
│   │   │   └── settings/page.tsx         帳號資訊
│   │   ├── audit/page.tsx                Brand AI Audit（2-step form + 報告）
│   │   ├── pricing/page.tsx              三級方案 + FAQPage Schema
│   │   ├── faq/[category]/page.tsx       動態 FAQ（5 個 audience × 10 Q&A）
│   │   ├── tools/
│   │   │   ├── page.tsx                  工具索引
│   │   │   ├── brand-check/page.tsx      Typeform 健檢入口
│   │   │   └── entity-builder/page.tsx   GEO Entity Builder
│   │   ├── about/page.tsx                關於
│   │   ├── checkout/
│   │   │   ├── success/page.tsx
│   │   │   └── cancel/page.tsx
│   │   ├── schema-generator/page.tsx     Schema + Wikidata generator
│   │   └── api/
│   │       ├── agent/route.ts            AI agent (vercel AI SDK)
│   │       ├── bci/[brand]/route.ts      公開 BCI API
│   │       ├── checkout/route.ts         Stripe session
│   │       ├── scan/route.ts             Free scan lead capture
│   │       ├── schema/route.ts           Schema generator API
│   │       └── webhooks/
│   │           ├── stripe/route.ts       Stripe webhook（付款 → geo-audit）
│   │           └── typeform/route.ts     Typeform webhook（表單 → leads）
│   ├── components/
│   │   ├── Navigation.tsx                sticky header + 手機選單 + 登入狀態
│   │   ├── Footer.tsx                    3 欄頁尾 + 合規聲明
│   │   ├── AuditForm.tsx                 2-step 10-field + 10s 動畫
│   │   ├── AuditReport.tsx               BCI 環 + 雷達 + 4 bar + PDF
│   │   ├── FreeScanForm.tsx              舊版健檢表單
│   │   ├── TypeformEmbed.tsx             Typeform 嵌入
│   │   ├── SchemaWikidataGenerator.tsx
│   │   └── auth/LoginForm.tsx            共用登入/註冊表單
│   ├── lib/
│   │   ├── scoring.ts                    BCI 引擎（TypeScript）
│   │   ├── faq-data.ts                   FAQ 知識庫 (5 × 10)
│   │   ├── agent/                        AI agent 工具
│   │   ├── email/resend.ts               Resend 客戶端
│   │   ├── github/dispatch.ts            repository_dispatch 觸發
│   │   ├── schema/generator.ts           Schema.org 產生器
│   │   ├── stripe/client.ts              Stripe 客戶端
│   │   └── supabase/
│   │       ├── server.ts                 server client
│   │       ├── client.ts                 browser client
│   │       └── middleware.ts             session refresh + gate
│   ├── middleware.ts                     Next.js middleware
│   ├── types.d.ts                        html2pdf.js declaration
│   ├── public/
│   │   ├── faq/                          舊版 FAQ 靜態 HTML（仍保留）
│   │   ├── llms.txt                      AI crawler canonical summary
│   │   ├── robots.txt                    crawler 授權
│   │   └── sitemap.xml
│   ├── package.json
│   ├── .npmrc                            legacy-peer-deps=true
│   ├── .env.example                      所有環境變數清單
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── next.config.js
│   └── vercel.json
│
├── apps/symcio-brand-audit/              ← 🚀 Netlify 備援靜態版
│   ├── index.html / report.html / pricing.html
│   ├── css/style.css
│   └── js/scoring-v2.js + charts.js + pdf-generator.js + analytics.js
│
├── supabase/
│   └── migrations/
│       ├── 20260417000000_initial_schema.sql     7-層 schema
│       ├── 20260421000000_geo_audit_queue.sql
│       ├── 20260422000000_bci_snapshots.sql       BCI 時序
│       └── 20260422000001_members_audit_history.sql  會員 + 歷史
│
├── scripts/
│   ├── geo_audit.py                      4 引擎可見度測試（含 email 閉環）
│   ├── bci_engine.py                     BCI 每日 snapshot
│   ├── bci_calibrate.py                  權重 grid search + Spearman
│   ├── collect_fixtures.py               InterBrand / Kantar CSV 合併
│   ├── providers/                        yfinance / alphavantage / mops_tw / bloomberg_stub
│   ├── prepare_content.sh                Medium / LinkedIn 發布準備
│   ├── composio_hubspot_sync.py
│   ├── notion_sync.py
│   ├── figma_sync.py
│   └── tests/                            48 unittest
│
├── .github/workflows/
│   ├── geo-audit.yml                     paid-audit + free-scan-request trigger
│   ├── bci-daily.yml                     BCI cron 03:00 TPE
│   ├── bci-test.yml                      pytest CI
│   ├── composio-hubspot-sync.yml         CRM 同步 cron
│   ├── notion-sync.yml
│   ├── figma-sync.yml
│   ├── supabase-ci.yml
│   └── supabase-deploy.yml
│
├── content/
│   ├── README.md                         發布索引 + 2 週 cadence
│   ├── medium/
│   │   ├── bci-the-ai-era-brand-capital-index.md
│   │   └── ai-brand-visibility-the-new-seo.md
│   ├── linkedin/
│   │   ├── bci-launch-post.md
│   │   └── day-6-close-post.md
│   ├── reddit/day-5-q-and-a.md
│   ├── x-twitter/day-4-threads.md
│   └── cold-outreach/
│       ├── README.md                     法律框架（GDPR / CAN-SPAM / 個資法）
│       ├── 01-interbrand-cmo.md
│       ├── 02-kantar-cmo.md
│       ├── 03-agency-partner.md
│       ├── 04-investor-pe-vc.md
│       ├── 05-esg-audit-firm.md
│       └── 06-saas-peer.md
│
├── docs/
│   ├── PRODUCT_OVERVIEW.md               本文件
│   ├── WAKE_UP_CHECKLIST.md              部署步驟
│   ├── DESIGN_SYSTEM.md                  視覺設計令牌
│   ├── BCI_METHODOLOGY.md                公開抽象 + InterBrand 對照
│   ├── AUTH_MEMBER_SPEC.md               會員系統提案
│   ├── SUPABASE_AUTH_SETUP.md            Auth 一步步設定
│   ├── TYPEFORM_SETUP.md                 Typeform webhook
│   ├── STRIPE_SETUP.md                   Stripe 設定
│   ├── DOMAIN_DEPLOY.md                  域名 DNS
│   ├── FULFILLMENT.md                    $299 付款後流程
│   ├── MVP_SPEC.md
│   ├── POSITIONING.md
│   └── 7_DAY_ATTACK.md                   發布策略
│
├── private/bci/                          ← 🔒 核心 IP（gitignored）
│   ├── README.md
│   ├── CALIBRATION.md                    校準程序
│   ├── weights_v1.example.json
│   └── inputs/README.md                  CSV 來源說明
│
├── database/schema.md                    文字版 schema 說明
├── llms.txt
├── README.md                             repo 入口
└── CLAUDE.md                             對 AI 代理的指令
```

---

## 三、使用者旅程 × 系統對應

### 🟢 第一次訪客（陌生人）

```
Google / AI 推薦 → https://symcio.tw
  ↓
首頁（Navigation 渲染 4 板塊 + BCI 公式 + 6 模組）
  ↓
點「免費品牌 AI 健檢」→ /audit
  ↓
AuditForm（2-step 10 欄）→ 10 秒診斷動畫 → AuditReport
  ↓
BCI 環 + 雷達 + 4 引擎 + GEO + 競品 + 建議
  ↓
「登入後自動儲存」banner → 點「免費註冊」→ /signup
```

### 🟢 會員（已登入）

```
/audit 完成 → SaveBanner 顯示「✓ 已儲存」→ audit_history INSERT（RLS）
  ↓
/dashboard Overview 統計 + 最近 5 筆
  ↓
/dashboard/history 完整時序表
  ↓
/dashboard/settings 看帳號資訊
```

### 🟢 $299 付費客戶

```
/pricing → 點專業版 → mailto（目前）／未來直接 Stripe Checkout
  ↓
Stripe 結帳 → webhook → orders INSERT + Resend 確認信
  ↓
repository_dispatch('paid-audit') → geo-audit.yml 跑
  ↓
scripts/geo_audit.py 跑 4 引擎 × 20 prompts
  ↓
視覺化報告 → Resend 寄 PDF 給客戶 → orders.status = 'completed'
```

### 🟢 BCI 時序（每日 cron）

```
.github/workflows/bci-daily.yml 03:00 TPE
  ↓
scripts/bci_engine.py：讀 brands → 各品牌取 F/V/E → BCI_WEIGHTS_JSON
  ↓
INSERT bci_snapshots（記錄 weights_version）
  ↓
公開 API：GET /api/bci/:brand → { total_bci, updated_at }
  （子項與權重不暴露）
```

### 🟢 冷信獲客（手動 1-to-1）

```
對方品牌名 → BRAND_NAME=X python scripts/geo_audit.py
  ↓
avg_score + mention_rate 當 hook
  ↓
從 content/cold-outreach/ 選 persona → 客製 [[個人化段落]]
  ↓
人工寄（≤ 20 封/日）→ CRM log
```

---

## 四、技術棧摘要

| 層 | 技術 | 備註 |
|----|------|------|
| Frontend | Next.js 14 App Router + React 18 + TypeScript 5 strict | `web/landing/` |
| Styling | Tailwind CSS 3.4 + CSS-in-JS（<style jsx>）偶爾 | 見 `docs/DESIGN_SYSTEM.md` |
| Charts | Chart.js 4.5 + react-chartjs-2 5.3 | radar + horizontal bar |
| PDF | html2pdf.js 0.10 + jsPDF | A4 portrait client-side |
| Database | Supabase Postgres 15 + RLS | 24 tables 7 layers |
| Auth | Supabase Auth (Email + Google OAuth) + @supabase/ssr | cookies-based |
| Payments | Stripe SDK v22 + Checkout + webhook HMAC | apiVersion 2026-03-25.dahlia |
| Email | Resend REST（stdlib fetch）| 付款確認 + 報告寄送 |
| AI Engines | OpenAI / Anthropic / Gemini / Perplexity REST | scripts/geo_audit.py |
| Analytics | GA4（G-QPB9W2885C）+ HubSpot | Script tags in layout |
| CI/CD | GitHub Actions + Vercel | 8 workflows |
| Deployment | Vercel (web/landing) + Netlify (apps/symcio-brand-audit) | 兩套 MVP 並存 |
| Market data | yfinance / alphavantage / mops_tw / bloomberg stub | pluggable MarketDataProvider |
| Package manager | npm | `.npmrc` legacy-peer-deps=true |

---

## 五、Schema.org / SEO 清單

| 頁面 | JSON-LD | 說明 |
|------|---------|------|
| 全站 layout | `Organization` | name + alternateName + sameAs（Wikidata / GitHub / Discord）|
| /pricing | `FAQPage` | 3 Q&A |
| /faq/[category] | `FAQPage` | 每 category 10 Q&A |
| apps/symcio-brand-audit/pricing.html | `FAQPage` | MVP 備援 |
| public/faq/*/index.html | `FAQPage` | 靜態 FAQ 備援 |

其他 SEO 元件：
- `public/robots.txt` 授權 GPTBot / ClaudeBot / PerplexityBot
- `public/llms.txt` AI canonical summary
- `public/sitemap.xml` 靜態 sitemap
- Open Graph + Twitter Card meta tags on all pages
- GA4 `G-QPB9W2885C` 全站載入

---

## 六、合規邊界（CLAUDE.md §1 明訂）

- ❌ Bloomberg / InterBrand / Kantar / SimilarWeb / SEMrush **不宣稱合作**
- ✅ 僅作為**類比座標**（nominative fair use）說明 Symcio 品類定位
- ❌ 冷信**絕不批量自動化**（`content/cold-outreach/README.md`）
- ✅ 1-to-1 人工個人化 ≤ 20/日
- ❌ BCI 權重向量**不進 repo**（`.gitignore` `private/bci/weights_*.json`）
- ✅ BCI 公式抽象公開於 `docs/BCI_METHODOLOGY.md`
- ❌ 公開 API 不暴露 BCI 子分數（F / V / E）與權重
- ✅ 只回 `total_bci` + `updated_at`

---

## 七、這個產品目前的 TRL（Technology Readiness Level）

| 組件 | TRL | 狀態 |
|------|-----|------|
| 官網 L1 | **9** | Production-ready，Next.js build 綠 |
| 會員系統 L2 | **8** | 程式完成；需跑 migration + Google OAuth 配置才生效 |
| Stripe 付款 L3 | **7** | 程式完成；需 Stripe Live keys + webhook secret |
| GEO Audit L4 | **8** | 每日 cron 就緒；需 API keys |
| BCI engine L5 | **8** | 引擎完成；需權重 calibration 才生產級 |
| 行銷內容 L6 | **9** | 內容備好，`bash scripts/prepare_content.sh` 一鍵發布 |

→ **整體產品 TRL 8**：所有程式碼就緒，只差**外部配置**（API keys、migration、DNS）。

---

## 八、下一輪可能的動作

按商業影響力排序：

| 優先 | 動作 | 工期 | 影響 |
|------|------|------|------|
| P0 | 部署到 symcio.tw 並公開 | 1 小時 | 打開轉換漏斗 |
| P0 | BCI weight calibration 跑真實資料 | 半天 | IP 核心可信度 |
| P1 | Stripe subscription 接專業版 recurring | 一天 | 自動續費營收 |
| P1 | Quota reset cron + 配額升級通知 email | 半天 | 轉換 free → paid |
| P2 | 雙語化 `/en` 路由 | 半天 | 國際市場 |
| P2 | Dashboard「AI 行銷建議」每日 LinkedIn 草稿 cron | 一天 | 留存 + 差異化 |
| P3 | 刪除帳號 / 改 email / 2FA | 半天 | 合規 |
| P3 | Enterprise SAML / SSO | 2 天 | 企業客戶需求 |
