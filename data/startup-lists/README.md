# 歷史名單匯入目錄

## 目的

放從 Excel / Google Sheets / HubSpot 匯出的歷史名單 CSV。灌進 Supabase 後：
- `leads` 表有完整資料 + source 標籤
- `brands` 表有對應 row（`status=prospect` + `priority=10` + `segment_tags`）
- `geo-audit-queue.yml`（每小時）會**按 priority 優先掃**這批，高於後來從網站進來的 lead

## PII 不進 Repo

這個目錄的 `*.csv` / `*.xlsx` / `*.tsv` 被 `.gitignore` 擋住，**不會被 commit**。放心丟你的客戶名單進來處理。

只有這份 `README.md` 跟 `.gitkeep` 會進 repo。

## 使用流程

### 1. 從 Google Sheets 下載 CSV

- Google Sheets → **File → Download → Comma-separated values (.csv)**
- 若有多個工作表，每個分別下載（或先合併成一個）
- 放進 `data/startup-lists/` 底下，命名例如 `verity-startup-meta-2026.csv`

### 2. 先 dry-run 驗解析

```bash
python scripts/import_brand_list.py data/startup-lists/verity-startup-meta-2026.csv \
    --col-brand '公司名稱' \
    --col-email 'Email' \
    --col-domain '網站' \
    --col-industry '產業' \
    --col-contact '聯絡人' \
    --col-phone '電話' \
    --segment startup-meta-2026 \
    --priority 10 \
    --dry-run
```

script 會印：
- Headers 偵測到的欄位名
- 每筆解析結果（公司 / email / 網域 / 產業 / priority）
- Summary：總筆數 / 無 email / 重複 / 會寫入幾筆

**重要**：Headers 印出來後若找不到你給的 `--col-*` 名稱，script 會 abort。檢查名稱是否跟 CSV 第一列完全一致（空白、半形全形差一個字都不行）。

### 3. 真的寫入

確認 dry-run 沒問題 → 拿掉 `--dry-run`：

```bash
export SUPABASE_URL="https://xxx.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="eyJ..."

python scripts/import_brand_list.py data/startup-lists/verity-startup-meta-2026.csv \
    --col-brand '公司名稱' \
    --col-email 'Email' \
    --col-domain '網站' \
    --col-industry '產業' \
    --segment startup-meta-2026 \
    --priority 10
```

寫完 Summary 印出：
- `leads_inserted` = 新增幾筆 lead
- `brands_inserted` / `brands_updated` = 品牌端新增 or 補 tag
- `no_email` / `invalid_email` / `dup_email` = 被跳過的原因

### 4. 下班 geo-audit-queue 自動接手

`priority=10` 的品牌會在下班 cron（每小時整點）優先被掃，因為 `fetch_prospects()` 已改成：

```sql
ORDER BY priority DESC, last_scanned_at NULLS FIRST, created_at ASC
```

預設新進來的 lead `priority=0`，所以這批 `priority=10` 會**永遠排在前面**直到全部掃完。

## 命名約定

`--segment` 的值會同時：
- 寫入 `leads.source`（方便 HubSpot segment 用）
- 加到 `brands.segment_tags[]`（PostHog 可以 cohort targeting）
- 寫入 `brands.source_list`（SQL query 方便）

推薦格式：`<list-name>-<time>`，例：
- `startup-meta-2026`
- `listed-esg-q2-2026`
- `sports-sponsor-2026`
- `verity-2026-may`

同一品牌多次匯入 → `segment_tags` 會 **append**（不覆寫），priority 會更新為最新值。這樣你可以先用 `verity-2026-may` 進，之後再用 `startup-meta-2026` 進同一批，兩個 tag 都保留。

## PostHog cohort targeting（A/B 打這批 lead）

匯入完成後，PostHog feature flag 可以條件：

```
IF person.segment_tags CONTAINS 'startup-meta-2026'
  → 這批 lead 看到 variant B（例如 web3_prominence = visible）
ELSE
  → 其他人看 variant A
```

具體 PostHog 後台怎麼設見 `docs/AB_TESTING_POSTHOG.md` §目標受眾分群。

## 欄位 mapping 速查

| 你的 CSV 欄位（典型中文）| `--col-*` 參數 | 寫到哪 |
|-----|-----|-----|
| 公司名稱 / 品牌名 | `--col-brand` | `leads.company` + `brands.name` |
| Email / 電子郵件 | `--col-email` | `leads.email` + `brands.primary_email` |
| 網站 / 網域 / URL | `--col-domain` | `brands.domain` |
| 產業 / 行業 | `--col-industry` | `brands.industry` |
| 聯絡人 / 窗口 | `--col-contact` | `leads.name` |
| 電話 | `--col-phone` | `leads.notes`（不進 brands）|
| 備註 / Notes | `--col-notes` | 附加到 `leads.notes` |

沒給 `--col-domain` / `--col-industry` 等 → 該欄位留 null，不影響。

## 常見錯誤

| 症狀 | 原因 | 對策 |
|------|------|------|
| `必要欄位 '...' 不在 CSV 裡` | header 名稱拼錯 | 看 script 印的 `Headers found` 複製貼上 |
| 所有 row 都 `no_email` | email 欄位名錯、或 email 在標題列之外 | CSV 第一列必須是 headers |
| 中文亂碼 | CSV 不是 UTF-8 | Excel 匯出請選「CSV UTF-8」；Google Sheets 匯出本身就 UTF-8 |
| `HTTP 403` on Supabase | SERVICE_ROLE_KEY 錯或 RLS 擋 | 確認用的是 service role（不是 anon）|
| 大量 `brands_updated` 不是 inserted | 該品牌名稱 brand 已存在 | 正常，script 會合併 tag 不覆寫原資料 |

## 後續清理

匯入完成且 geo-audit-queue 跑完一輪後：
- 想調整 priority → 直接 Supabase Studio `brands` 表改
- 想移除某 segment → 在 SQL 下 `UPDATE brands SET segment_tags = segment_tags - 'xxx'`
- CSV 本身處理完可以**從本機刪除**（已在 Supabase 裡了，PII 不用留兩份）
