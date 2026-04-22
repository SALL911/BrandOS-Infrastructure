# Typeform Free Scan Pipeline 設定

Typeform 表單 `ZZYlfK7A` 是 Symcio Free Scan 的入口。這份文件說明從使用者提交到報告寄出的完整管線設定。

## 完整資料流

```
User
  ↓ 填寫 https://form.typeform.com/to/ZZYlfK7A
[Typeform]
  ↓ Webhook POST（帶 Typeform-Signature header）
[Vercel: /api/webhooks/typeform]
  ↓ ① HMAC-SHA256 驗簽
  ↓ ② 解析答案（brand_name / email / industry / ...）
  ↓ ③ INSERT Supabase `leads`（= 佇列）
  ↓ ④ GitHub repository_dispatch "free-scan-request"
[GitHub Actions: geo-audit.yml]
  ↓ 跑 4 引擎 AI 測試（ChatGPT / Claude / Gemini / Perplexity）
  ↓ 寫 Supabase `visibility_results`
  ↓ （未來）觸發報告生成 + Resend 寄信
[Resend] → User 收到 email 報告

＋ 並行：
[GitHub Actions: composio-hubspot-sync.yml]（每小時 cron）
  ↓ 讀 Supabase `leads` 新紀錄
  ↓ Composio → Notion / HubSpot
```

## 設定步驟

### 1. 在 Typeform 設定 field refs（一次性）

為了讓 webhook 正確解析欄位，**每個問題都要設 Reference**（不是預設的 random hash）。

到 https://admin.typeform.com/form/ZZYlfK7A/create →
每題右側 **⋯ → Question settings → Reference**，設成對應值：

| 問題 | Reference（必須完全一致）|
|------|-------------------------|
| Email 欄位 | `email` |
| 品牌名稱 | `brand_name` |
| 品牌網域 | `brand_domain` |
| 產業類別 | `industry` |
| 公司名稱 | `company` |

備援：若 ref 沒設，webhook 會用題目標題做 fuzzy match（含「品牌」「網域」「產業」「公司」「email」字樣）。

### 2. 產生 webhook secret

```bash
# 本機任何 terminal
openssl rand -base64 32
```

複製輸出（~44 字元）。

### 3. 在 Vercel 設 secrets

Vercel → symcio project → Settings → Environment Variables（Production + Preview）：

| Key | Value |
|-----|-------|
| `TYPEFORM_WEBHOOK_SECRET` | 步驟 2 產生的字串 |
| `SUPABASE_URL` | 已有（Supabase API 頁）|
| `SUPABASE_SERVICE_ROLE_KEY` | 已有 |
| `GH_DISPATCH_TOKEN` | 已有（GitHub PAT with `repo` scope）|
| `GH_DISPATCH_REPO` | `SALL911/BrandOS-Infrastructure` |

設完 → **Redeploy**（env 變更不會自動生效）。

### 4. 在 Typeform 設定 webhook

https://admin.typeform.com/form/ZZYlfK7A/connect → **Webhooks** → **Add a webhook**：

- **Endpoint URL**：`https://symcio.tw/api/webhooks/typeform`
- **Secret**：步驟 2 同一個 32 字元字串（Typeform 用來算 HMAC）
- **Enabled**：ON
- Save

Typeform 會送一次測試請求。預期回應：

```json
{"ok": true, "event": "form_response", "lead_id": "uuid", "warnings": []}
```

若回 `401 invalid-signature`：secret 兩邊對不上，重做步驟 2–4。

### 5. 驗證端到端

1. 打開 https://symcio.tw/tools/brand-check（應該看到 Typeform 嵌入）
2. 真的填一份表單
3. **5 秒內**：Supabase `leads` 表應該有新紀錄，`source='typeform-ZZYlfK7A'`
4. **10 秒內**：GitHub Actions → `GEO Audit` workflow 被 `free-scan-request` event 觸發
5. **3 分鐘內**：workflow 綠燈，`reports/geo-audit/{brand}-{date}.json` 產生（或寫入 Supabase `visibility_results`）
6. **下一次 cron 或手動觸發**：Composio `hubspot-sync` 把 lead 寫入 Notion

## 除錯

### Typeform 顯示 `401 invalid-signature`
- `TYPEFORM_WEBHOOK_SECRET` 和 Typeform 那邊設的不一樣
- Vercel env 改了但沒 redeploy

### 收到 webhook 但 lead 沒進 Supabase
- Response body 看 `warnings[]`：
  - `supabase-not-configured` → env 沒設
  - `supabase: ...` → RLS 或 schema 問題，檢查 `leads` table policies

### webhook 成功但 GitHub Actions 沒跑
- `warnings[]` 有 `dispatch: github HTTP 401` → PAT 過期
- `warnings[]` 有 `dispatch: github HTTP 422` → `event_type` 拼錯（webhook 送的是 `free-scan-request`，workflow 的 `types:` 要包含它）

### 表單填完後使用者卡在 Typeform
- Typeform 可設 redirect_on_completion → `https://symcio.tw/checkout/success?free_scan=true`
- 或在 Typeform 完成頁顯示「報告將於 3 分鐘內寄到你的 email」

## 欄位對應：如何改 Typeform 不改 code

`app/api/webhooks/typeform/route.ts` 的 `extractFields()` 以 **ref 為主、title fuzzy match 為備**。

推薦流程：
1. 在 Typeform 新增或改名題目
2. 在該題設定 `ref`（見步驟 1 對照表）
3. 不需動 code
4. 若是**全新欄位**（例如加 `phone`），需要在 webhook code 裡新增 case——開 issue 或改 code。

## 後續 Phase 2（未做）

- [ ] 報告完成後自動 Resend 寄 email（目前 `/api/agent` 有這邏輯，typeform webhook 尚未接）
- [ ] `typeform_token` 用來去重（同一提交不重跑）
- [ ] Typeform `hidden` fields 接 UTM 參數
- [ ] Typeform `partial_response` event 接「開始填但沒送完」的 lead 做 re-engagement
