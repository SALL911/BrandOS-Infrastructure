# AIVI 事實正確性｜使用手冊

> 對應程式：`scripts/aivi_accuracy.py`（判定）、`scripts/aivi_tracker.py`（採樣）
> 對應排程：`.github/workflows/aivi-weekly.yml`
> 方法版本：`acc-v1`

---

## 一、WHY：為什麼要量「講對沒有」

提及率只回答「AI 有沒有講到你」。客戶真正會付錢處理的是「AI 講錯你」：

| 錯誤類型 | 代號 | 例子 | 對應補救 |
|---|---|---|---|
| 錯誤主張 | `wrong_fact` | 「Symcio 是 Bloomberg 授權代表」 | 修正公開資訊來源、發布更正聲明 |
| 同名混淆 | `name_collision` | 「Symcio 是三陽旗下品牌」 | Wikidata／Organization schema 實體錨點 |
| 講不出事實 | `no_verifiable_fact` | 「Symcio 是一個品牌服務」 | 補官網結構化資料、LEI、NAP 一致性 |

這三類分別對應「企業全球數位身分建檔包」與「品牌證據包」的交付內容。量測的人不做補救（紅線：裁判不下場），補救交給夥伴執行。

---

## 二、WHAT：判定規則（acc-v1）

每一則**有提及品牌**的 AI 回覆，依品牌事實檔判定為：

| 結果 | 條件 |
|---|---|
| `correct` | 品牌名前後 150 字內，命中至少 1 項可查證事實，且沒有錯誤主張 |
| `partial` | 有提及，但講不出任何可查證事實 |
| `wrong` | 出現錯誤主張（非否定句），或在談同名的另一個實體 |
| `absent` | 沒提及；不計入正確率分母 |

**否定句不算錯**：「Symcio **並非** Bloomberg 授權代表」不會被判為錯誤；否定詞只在同一子句內有效，不會跨句。

**刻意不用 LLM 當裁判**：同一份回覆配同一版事實檔，永遠得到同一個結果，客戶和稽核者都能重現。規則是啟發式，仍須每月人工抽驗 10%（寫入 `aivi_mentions.verified_by`）。

---

## 三、HOW：操作步驟

### 1. 一次性設定（GitHub → Settings → Secrets and variables → Actions）

**Secrets**（至少一組引擎金鑰）：

| 名稱 | 用途 |
|---|---|
| `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `PERPLEXITY_API_KEY` | 四引擎；缺哪個就略過哪個 |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | 寫入資料庫，累積時間序列 |

**Variables**：

| 名稱 | 建議值 | 說明 |
|---|---|---|
| `AIVI_REPEATS` | 每週 `1`，月初基線 `3` | 同題重複次數；AI 回答有變異 |

**採樣量** = 題數 × 引擎數 × 重複次數。以 Symcio 示範組為例：80 題（中英各 40）× 4 引擎 × 1 次 = 每週 320 次 API 呼叫；`AIVI_REPEATS=3` 時為 960 次。請依各引擎計價自行估算成本。

### 2. 合併 PR

合併到 `main` 後，`supabase-deploy.yml` 會自動套用 `20261120000000_aivi_accuracy.sql`。**務必等這個 workflow 綠燈後再跑採樣**，否則新欄位寫不進去，tracker 會以 exit code 4 報錯（本機 JSON 報告仍會產出）。

### 3. 手動試跑

GitHub → Actions → **AIVI Weekly Tracking** → Run workflow：

1. 先用 `dry_run = true`：只印採樣計畫，不花錢
2. 再用 `dry_run = false`、`run_type = baseline`：正式取樣

之後每週一台北 09:00 自動執行。

### 4. 看結果

- **快速看**：該次 Run 的終端輸出最後一行
  `正確率 X%｜講不出事實 Y%｜講錯 Z%｜錯誤類型 {...}`
- **完整明細**：Run 頁面下方 Artifacts → `aivi-<run_id>` → JSON，每筆含 `accuracy`、`error_type`、`facts_matched`、`conflicts_found`、原始回覆
- **月趨勢**：Supabase SQL Editor

```sql
SELECT period, accuracy_method, scored, correct_rate_pct, wrong_rate_pct,
       name_collisions, wrong_facts
FROM v_aivi_accuracy_monthly
WHERE brand_id = '<brands.id>'
ORDER BY period DESC;
```

`accuracy_method` 不同的月份不可直接比較（事實檔升版了）。

### 5. 本機跑（不經 GitHub）

```bash
DRY_RUN=true python scripts/aivi_tracker.py                 # 看計畫
GEMINI_API_KEY=xxx AIVI_REPEATS=3 python scripts/aivi_tracker.py
python -m pytest -q tests/test_aivi_accuracy.py             # 規則測試
```

---

## 四、新增客戶品牌

1. **先簽約**：`TRACKING_STATUS=poc` 或 `subscription` 時，沒有 `AIVI_CONSENT_REF` 與 `AIVI_DPA_ID` 會拒絕採樣
2. **用私有 repo**：本 repo 是 public，Artifacts 與 log 都看得到。客戶追蹤請在私有 repo 執行同一套 workflow
3. **事實檔走 Secret**：照 `prompts/symcio/facts.json` 的格式寫好客戶事實檔，整份 JSON 貼進 Secret `AIVI_FACTS_JSON`，不要 commit
4. **事實檔要客戶確認**：每一項事實都必須有公開出處，由客戶書面確認後才能用來判定「講錯」

### 事實檔欄位

| 欄位 | 內容 |
|---|---|
| `version` | 改內容就升版，例 `acme-facts-v2` |
| `brand_terms` | 品牌名、別名、域名；用來判斷事實是否歸屬於本品牌 |
| `facts` | 可查證事實；`any_of` 填多種寫法（中英文、簡稱） |
| `wrong_claims` | 已知的錯誤說法，命中即判 `wrong_fact` |
| `confusables` | 易混淆的同名實體 |

---

## 五、限制聲明（報告必附）

- 採樣走官方 API，不等同 ChatGPT／Gemini 消費者版畫面（消費者版可能有聯網搜尋與個人化）
- 判定為關鍵字規則，可能漏判改寫過的錯誤說法；已以人工抽驗補強
- 量測結果不構成對品牌價值、合規狀態或確信的意見
