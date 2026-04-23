# 歷史名單優先掃描 + A/B 對特定 segment 打

## 情境

Symcio 在網站開張前，手上已有名單（新創 Meta 名單、Verity 開發名單、
行業聯絡簿、HubSpot Export 等）。要讓這些名單：

1. 灌進 Supabase leads / brands（當作 BrandOS 的種子）
2. 被 geo-audit-queue **優先掃描**（高於網站新進 lead）
3. 在 PostHog A/B 實驗裡被當成一個 **獨立 cohort** 打差別化文案
4. 全程**不把 PII 寫進 repo**（Git 永遠不知道他們是誰）

本 PR 把這條 pipeline 打通。

## 全貌

```
┌────────────────────────────────────────────────────────────┐
│ Google Sheets / Excel / HubSpot export                     │
│  ↓ File → Download → CSV                                   │
│ data/startup-lists/verity-2026-may.csv（gitignored）       │
│  ↓ python scripts/import_brand_list.py --segment ...       │
│    --priority 10                                            │
│                                                             │
│ Supabase                                                    │
│  ├─ leads (source='startup-meta-2026', notes=...)          │
│  └─ brands (status='prospect', priority=10,                │
│              segment_tags=['startup-meta-2026'],            │
│              source_list='startup-meta-2026')               │
│                                                             │
│ 每小時 cron：.github/workflows/geo-audit-queue.yml          │
│  ↓ fetch_prospects() ORDER BY priority DESC,                │
│    last_scanned_at NULLS FIRST                              │
│                                                             │
│ 先掃 priority=10 的歷史名單，再掃 priority=0 的新 lead      │
│  ↓                                                          │
│ Mitake 簡訊 / Gmail Free Scan 報告                          │
│                                                             │
│ PostHog 後台                                                │
│  ↓ Feature flag 條件：                                       │
│    IF person.segment_tags contains 'startup-meta-2026'     │
│      → variant B（web3_prominence=visible, hero=esg_ai_dual）│
│    ELSE → variant A                                         │
│                                                             │
│ Meta Ads Manager                                            │
│  ↓ UTM：utm_source=fb&utm_campaign=startup-meta-2026&       │
│         utm_content=hero-esg                                 │
│  → 帶他們回站 → leads.utm_campaign 可對應 → PostHog          │
│     person property 吻合 → 看到對應變體                      │
└────────────────────────────────────────────────────────────┘
```

## 變更

### Migration：`brands` 表加 4 欄 + 3 索引
```sql
ALTER TABLE brands
  ADD COLUMN segment_tags JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN priority     SMALLINT DEFAULT 0,
  ADD COLUMN imported_at  TIMESTAMPTZ,
  ADD COLUMN source_list  VARCHAR(100);

-- priority DESC + last_scanned_at NULLS FIRST
CREATE INDEX idx_brands_priority_scan ON brands(priority DESC, last_scanned_at NULLS FIRST)
  WHERE status = 'prospect';

CREATE INDEX idx_brands_segment_tags ON brands USING GIN (segment_tags);
CREATE INDEX idx_brands_source_list ON brands(source_list) WHERE source_list IS NOT NULL;
```

### 新：`scripts/import_brand_list.py`
Zero-dep（stdlib csv + urllib），彈性 column mapping，dry-run 支援，dedupe by email。

### 改：`scripts/geo_audit_queue.py`
`fetch_prospects()` 的 ORDER BY 從 `created_at ASC` 改為：

```
priority DESC,
last_scanned_at NULLS FIRST,
created_at ASC
```

Log 行也會印 priority 與 tags：
```
── Verity Corp (saas) [pri=10 tags=startup-meta-2026] ──
```

### 新：`data/startup-lists/` 目錄 + gitignore
`.csv` / `.xlsx` / `.tsv` 不進 repo，只有 README.md 結構說明進。

### 新：`docs/STARTUP_LIST_PIPELINE.md`（本文件）

## 使用流程（5 步）

### 1. 下載 Google Sheets → CSV（30 秒）
File → Download → **Comma-separated values (.csv)** → 存到 `data/startup-lists/`。

### 2. Dry-run 驗解析（1 分鐘）
```bash
python scripts/import_brand_list.py data/startup-lists/verity-2026.csv \
    --col-brand '公司名稱' \
    --col-email 'Email' \
    --col-industry '產業' \
    --segment startup-meta-2026 \
    --priority 10 \
    --dry-run
```
看 Summary：確認解析到正確筆數。

### 3. 真的寫入（2–5 分鐘，視筆數）
拿掉 `--dry-run`，再跑一次。

### 4. 觸發 geo-audit-queue 手動跑（5 分鐘）
不想等下班整點 → GitHub Actions → **GEO Audit Queue** → Run workflow →
`dry_run: true` 先驗 → `dry_run: false` 真跑。

你會看到 log 最上面先出現 `[pri=10 ...]` 的品牌，下面才是 `[pri=0]`。

### 5. PostHog 設 cohort targeting
PostHog → Feature Flag（e.g. `hero_headline`）→ **Persons who match** →
Person property `segment_tags` `contains` `"startup-meta-2026"` → Rollout 100% `esg_ai_dual`。

其他人走預設 50/50。

## 與 5 個 A/B 實驗的對應

| Flag | 對 `startup-meta-2026` 預期 variant | 原因 |
|------|--------------------------------|------|
| `hero_headline` | `esg_ai_dual` | 新創 meta 對 ESG + AI 雙敘事接受度通常高於純 AI |
| `primary_cta` | `free_scan` | 新創節奏快，不想約 demo |
| `web3_prominence` | `visible` | meta 新創重疊 Web3 受眾 |
| `pricing_display` | `progressive` | 預算通常較緊，不想看 $12k 選項嚇跑 |
| `primary_narrative` | `esg_first` | 同 hero_headline |

這只是**初始假設**，跑兩週看 PostHog 顯著性再調整。

## Meta Ads 對應（給這批 lead 的素材）

UTM 約定：
```
https://symcio.tw/audit?
  utm_source=facebook
  &utm_medium=paid-social
  &utm_campaign=startup-meta-2026    ← 跟 segment 同名
  &utm_content=hero-esg              ← variant key
  &utm_term=startup-ai-visibility
```

PostHog person property `utm_campaign = 'startup-meta-2026'` →
自動被當作 `startup-meta-2026` cohort 成員看 variant B（等同直接進 segment）。

## SQL：查這批 lead 的漏斗

```sql
-- 這批 lead 裡，多少已經被掃過
SELECT 
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE last_scanned_at IS NOT NULL) AS scanned,
  COUNT(*) FILTER (WHERE first_scan_sent_at IS NOT NULL) AS emailed,
  AVG(EXTRACT(EPOCH FROM (last_scanned_at - imported_at)) / 3600) AS avg_hours_to_scan
FROM brands
WHERE 'startup-meta-2026' = ANY(
  SELECT jsonb_array_elements_text(segment_tags)
);
```

## 何時把 priority 降回 0？

這批全部 `first_scan_sent_at IS NOT NULL`（都寄完首次 Free Scan）之後：

```sql
UPDATE brands 
SET priority = 0 
WHERE source_list = 'startup-meta-2026'
  AND first_scan_sent_at IS NOT NULL;
```

把位子讓給新進來的 lead。不然 queue 永遠掃這批。

## Follow-up

1. 把 `segment_tags` 也 sync 到 HubSpot Contact property（透過 `composio-hubspot-sync.yml`）
2. SMS 功能 `sms_subscribers.segment_tags` 與這裡同步，campaign 可按 cohort 寄
3. Admin UI 顯示每個 segment 的漏斗狀態（目前要 SQL 手查）

## 相關檔案

- Migration：`supabase/migrations/20260425000000_brands_priority_segment.sql`
- 匯入工具：`scripts/import_brand_list.py`
- 匯入目錄：`data/startup-lists/`（gitignored）+ `data/startup-lists/README.md`
- Queue 優先序：`scripts/geo_audit_queue.py`（改 `fetch_prospects`）
- A/B cohort：`docs/AB_TESTING_POSTHOG.md` §目標受眾分群
- 廣告 UTM 對應：`docs/META_ADS_EXPERIMENT.md`
