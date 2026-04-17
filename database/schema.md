# BrandOS Infrastructure — Database Schema
## schema.md v1.0 | Symcio × BrandOS

---

## 概述（WHY）

本 schema 定義 BrandOS Infrastructure 的三層資料架構：
- Layer 1：品牌客戶基礎資料（Brand Profiles）
- Layer 2：BrandOS SaaS 平台運營數據
- Layer 3：AI 知識資產累積（Knowledge Assets）

資料庫技術棧：PostgreSQL（主要）/ SQLite（本機開發）

---

## Layer 1：Brand Profiles（品牌基礎資料）

### Table: brands

```sql
CREATE TABLE brands (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name            VARCHAR(255) NOT NULL,           -- 品牌名稱
  name_en         VARCHAR(255),                    -- 英文名稱
  industry        VARCHAR(100),                    -- 產業類別
  market          VARCHAR(100),                    -- 主要市場（台灣/亞太/全球）
  company_size    VARCHAR(50),                     -- 規模（SME/Enterprise）
  website         VARCHAR(500),                    -- 官網
  bloomberg_id    VARCHAR(100),                    -- Bloomberg 代碼（如有）
  status          VARCHAR(50) DEFAULT 'active',    -- active / inactive / prospect
  onboarded_at    TIMESTAMP DEFAULT NOW(),
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW()
);
```

### Table: esg_metrics

```sql
CREATE TABLE esg_metrics (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id        UUID REFERENCES brands(id) ON DELETE CASCADE,
  report_year     INTEGER NOT NULL,
  -- E: 環境指標
  carbon_emission DECIMAL(15,2),                  -- 碳排放量（tCO2e）
  energy_usage    DECIMAL(15,2),                  -- 能源使用量（MWh）
  water_usage     DECIMAL(15,2),                  -- 用水量（m3）
  waste_reduction DECIMAL(5,2),                   -- 廢棄物減量（%）
  -- S: 社會指標
  employee_count  INTEGER,
  gender_ratio    DECIMAL(5,2),                   -- 女性員工比例（%）
  training_hours  DECIMAL(10,2),                  -- 年均培訓時數
  -- G: 治理指標
  board_independence   DECIMAL(5,2),              -- 獨立董事比例（%）
  esg_report_published BOOLEAN DEFAULT FALSE,
  -- TNFD / LEAP 框架
  tnfd_disclosure JSONB,                          -- TNFD 揭露數據（結構化 JSON）
  leap_stage      VARCHAR(50),                    -- LEAP 框架階段
  esg_score       DECIMAL(5,2),                   -- ESG 綜合評分（0-100）
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW()
);
```

### Table: brand_scores（Brand Score AI 七維評分）

```sql
CREATE TABLE brand_scores (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id        UUID REFERENCES brands(id) ON DELETE CASCADE,
  scored_at       TIMESTAMP DEFAULT NOW(),
  identity_score  DECIMAL(5,2),   -- 品牌識別（0-100）
  geo_score       DECIMAL(5,2),   -- GEO 優化指數（0-100）
  esg_score       DECIMAL(5,2),   -- ESG 合規指數（0-100）
  digital_score   DECIMAL(5,2),   -- 數位資產指數（0-100）
  narrative_score DECIMAL(5,2),   -- 品牌敘事指數（0-100）
  market_score    DECIMAL(5,2),   -- 市場定位指數（0-100）
  trust_score     DECIMAL(5,2),   -- 信任資產指數（0-100）
  total_score     DECIMAL(5,2),   -- 綜合 Brand Score
  notes           TEXT,
  created_at      TIMESTAMP DEFAULT NOW()
);
```

---

## Layer 2：BrandOS SaaS（平台運營數據）

### Table: subscriptions

```sql
CREATE TABLE subscriptions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id        UUID REFERENCES brands(id) ON DELETE CASCADE,
  plan            VARCHAR(50) NOT NULL,   -- starter / growth / enterprise
  status          VARCHAR(50) DEFAULT 'active',
  started_at      TIMESTAMP NOT NULL,
  expires_at      TIMESTAMP,
  mrr             DECIMAL(10,2),          -- 月經常性收入（USD）
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW()
);
```

### Table: brand_projects（BrandOS 八階段進度追蹤）

```sql
CREATE TABLE brand_projects (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id        UUID REFERENCES brands(id) ON DELETE CASCADE,
  name            VARCHAR(255) NOT NULL,
  stage           INTEGER CHECK (stage BETWEEN 1 AND 8),
  -- Stage 1: 品牌診斷 Brand Audit
  -- Stage 2: 品牌定位 Brand Positioning
  -- Stage 3: 視覺識別 Visual Identity
  -- Stage 4: 敘事系統 Narrative System
  -- Stage 5: GEO 優化 GEO Optimization
  -- Stage 6: ESG 整合 ESG Integration
  -- Stage 7: 數位資產 Digital Assets
  -- Stage 8: 品牌治理 Brand Governance
  status          VARCHAR(50) DEFAULT 'in_progress',
  deliverables    JSONB,
  started_at      TIMESTAMP,
  completed_at    TIMESTAMP,
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW()
);
```

---

## Layer 3：AI Knowledge（知識資產累積）

### Table: knowledge_nodes（核心知識節點）

```sql
CREATE TABLE knowledge_nodes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id        UUID REFERENCES brands(id) ON DELETE SET NULL,
  node_type       VARCHAR(100) NOT NULL,
  -- node_type 選項：
  -- brand_analysis / geo_strategy / esg_compliance
  -- business_model / market_insight / ip_asset
  title           VARCHAR(500) NOT NULL,
  insight         TEXT NOT NULL,          -- 核心洞察（2-3句精確陳述）
  action_items    JSONB,                  -- 行動建議陣列
  source          VARCHAR(255),           -- 來源（對話/報告/研究）
  tags            TEXT[],
  is_public       BOOLEAN DEFAULT FALSE,
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW()
);
```

### Table: memory_contexts（跨 session 情境記錄）

```sql
CREATE TABLE memory_contexts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_date    DATE NOT NULL,
  context_type    VARCHAR(100),   -- daily_briefing / project_summary / decision_log
  brand_id        UUID REFERENCES brands(id) ON DELETE SET NULL,
  content         TEXT NOT NULL,
  key_decisions   JSONB,
  next_actions    JSONB,
  created_at      TIMESTAMP DEFAULT NOW()
);
```

### Table: geo_content（GEO 內容資產）

```sql
CREATE TABLE geo_content (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand_id        UUID REFERENCES brands(id) ON DELETE CASCADE,
  content_type    VARCHAR(100),   -- answer_engine / structured_data / knowledge_graph
  title           VARCHAR(500),
  content         TEXT NOT NULL,
  target_queries  TEXT[],         -- 目標查詢語句
  platforms       TEXT[],         -- 目標平台：ChatGPT / Perplexity / Gemini / Claude
  performance     JSONB,          -- 表現追蹤數據
  published_at    TIMESTAMP,
  created_at      TIMESTAMP DEFAULT NOW(),
  updated_at      TIMESTAMP DEFAULT NOW()
);
```

---

## 索引建議

```sql
CREATE INDEX idx_brands_status ON brands(status);
CREATE INDEX idx_brands_industry ON brands(industry);
CREATE INDEX idx_esg_metrics_brand_year ON esg_metrics(brand_id, report_year);
CREATE INDEX idx_knowledge_nodes_type ON knowledge_nodes(node_type);
CREATE INDEX idx_knowledge_nodes_tags ON knowledge_nodes USING GIN(tags);
CREATE INDEX idx_geo_content_queries ON geo_content USING GIN(target_queries);
```

---

## 版本紀錄

| 版本 | 日期 | 變更說明 |
|------|------|----------|
| v1.0 | 2026-04-17 | 初始版本，建立三層架構（Layer 1 / Layer 2 / Layer 3） |
