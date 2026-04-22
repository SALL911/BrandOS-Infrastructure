# Typeform 表單內容（form ZZYlfK7A）

直接複製貼到 Typeform admin。每題右側 **⋯ → Question settings → Reference** 要設對應的 ref（關鍵，webhook 靠這個解析）。

進入：https://admin.typeform.com/form/ZZYlfK7A/create

---

## 歡迎頁（Welcome Screen）

**Type**：Welcome screen
**Title**：
```
30 秒看見你的品牌在 AI 的真實位置
```
**Description**：
```
Symcio 會跨 ChatGPT、Claude、Gemini、Perplexity 四個 AI 引擎測試你的品牌曝光度，結果直接寄到你的信箱。完全免費、不需信用卡、不轉售名單。
```
**Button text**：`開始掃描 →`

---

## Q1 — 品牌名稱（必填）

**Type**：Short text
**Question**：
```
你的品牌名稱是？
```
**Description**：
```
會用於 AI 引擎查詢，請填最常對外使用的名字（中文或英文皆可，例如：Symcio / 全識 / Nike）。
```
**Required**：✅ On
**Reference** ← 設這個：
```
brand_name
```

---

## Q2 — Email（必填）

**Type**：Email
**Question**：
```
報告要寄到哪個 email？
```
**Description**：
```
我們只用來寄報告與後續追蹤，不會轉售。
```
**Required**：✅ On
**Reference**：
```
email
```

---

## Q3 — 品牌網域（選填）

**Type**：Website
**Question**：
```
品牌官網網域？（選填）
```
**Description**：
```
有網域有助於 AI 精準辨識品牌。例：symcio.tw
```
**Required**：❌ Off
**Reference**：
```
brand_domain
```

---

## Q4 — 產業類別（必填）

**Type**：Multiple choice（**單選**）
**Question**：
```
你的產業類別？
```
**Description**：
```
決定 Symcio 從 prompt 庫抽哪些產業代表性測試題。
```
**Required**：✅ On
**Reference**：
```
industry
```
**Choices**（**每個選項旁邊也要設 value**，給機器用的）：

| 選項顯示文字 | Value |
|-------------|-------|
| Technology / SaaS | `technology` |
| Finance / Fintech / 金融科技 | `finance` |
| Consumer Goods / 消費品 | `consumer_goods` |
| Professional Services / 顧問 / 諮詢 | `professional_services` |
| Manufacturing / 製造 | `manufacturing` |
| Other / 其他 | `default` |

> Typeform 在 Multiple Choice 設 value：點選項 → 右側齒輪 → **Set choice value**

---

## Q5 — 公司 / 組織名稱（選填）

**Type**：Short text
**Question**：
```
你代表的公司 / 組織是？（選填）
```
**Description**：
```
若品牌名與公司名不同（例：品牌「BrandOS」屬於「全識股份有限公司」），填這裡。個人創作者可直接填個人名。
```
**Required**：❌ Off
**Reference**：
```
company
```

---

## 結尾頁（End Screen）

**Type**：Ending / Thank You
**Title**：
```
已收到 — 掃描啟動中
```
**Description**：
```
Symcio 正在跨四引擎測試你的品牌。完整報告將於 30 分鐘內寄到你填的 email（含垃圾信夾）。

如 60 分鐘後仍未收到，來信 info@symcio.tw。
```
**Button text**：`返回 symcio.tw`
**Button link**：`https://symcio.tw`

---

## 完成後檢查

- [ ] 5 題 ref 全部設好：`brand_name` / `email` / `brand_domain` / `industry` / `company`
- [ ] Q4 的 6 個選項 value 全部設好（`technology` / `finance` / ...）
- [ ] 點 **Publish** 讓新版生效
- [ ] 開 https://form.typeform.com/to/ZZYlfK7A 自己填一次測試
- [ ] 送出後到 Vercel → symcio project → Logs 看 `/api/webhooks/typeform` 是否收到 200

---

## 對應 webhook 解析邏輯

Webhook `extractFields()` 用的順序：`ref` 優先，否則 title fuzzy match。設完 ref 後 **`extractFields()` 永遠 100% 命中**，不需要依賴 title 的模糊比對。

若你之後要加第 6 題（例如「主要競品」），告訴我 ref 名字，我再補 webhook 解析 case。
