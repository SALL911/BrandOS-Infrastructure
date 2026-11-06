# CRM × LINE × Meta 整合手冊
## docs/ai-team/crm-line-meta.md v1.0 | growth-operator 工具鏈

---

## 一、WHY：約束先行

| 約束 | 影響 |
|------|------|
| HubSpot、Attio 兩套 CRM 並存 | 最大風險是兩邊各改一半。規則：**Supabase 是唯一真相，兩套 CRM 只接收、不回寫** |
| 帳號註冊需本人完成 email 驗證、同意條款、設定 2FA | 助手不代為註冊；本文件列出本人要做的步驟 |
| Meta 規定一人只能有一個個人帳號 | 不開三個帳號。以 cchuan911@gmail.com 為主帳號，另兩個信箱設為備援 / 復原信箱 |
| 個人聯絡人（手機 / Gmail）未同意行銷 | 匯入 CRM 一律標「個人聯絡人、無行銷同意」，不得加入電子報、LINE 推播或自動序列 |
| LINE 好友只有 line_user_id，沒有 email / 電話 | 只能經 LINE Login 綁定會員後才對應到 CRM；未綁定的好友只計數、不入 CRM |

---

## 二、WHAT：資料流

```
symcio.tw 表單 / 會員註冊 / Typeform ─┐
LINE webhook（follow / message）──────┤→ Supabase（leads / members / line_followers）
                                      │
                                      ├→ HubSpot：composio-hubspot-sync.yml（leads）
                                      │           symcio.tw member-sync（members）
                                      └→ Attio：crm-sync.yml（leads + members，以 email 合併）

Gmail 往來 ──→ Attio 原生 Gmail 同步（自動建立人員 / 公司、記錄往來）
Gmail 往來 ──→ HubSpot 原生 Gmail 連線（記錄往來、會議）
手機聯絡人 ──→ Google 聯絡人（手機端設定）──→ 只進 Attio，標「個人聯絡人」

LINE / FB / IG 粉絲數 ──→ social-followers.yml ──→ social_follower_snapshots（每日）
```

---

## 三、HOW：本人要做的設定（依序）

### 3.1 Attio（約 10 分鐘）
1. 到 attio.com 以 **cchuan911@gmail.com** 註冊 workspace「Symcio」
2. Settings → Email & calendar → 連結 Gmail（cchuan911@gmail.com）
   - 同步範圍選「僅與公司網域往來」或手動排除私人往來，避免家人朋友進 CRM
3. Settings → Developers → 建立 API key，權限：`record_permission: read-write`、`object_configuration: read`
4. GitHub → BrandOS-Infrastructure → Settings → Secrets → 新增 `ATTIO_API_KEY`
5. Actions → CRM Sync → Run workflow：`dry_run=true` → `dry_run=false, limit=1` → 確認 Attio 出現該筆後恢復預設

### 3.2 HubSpot
- 已由 Composio 連線（`COMPOSIO_HUBSPOT_CONNECTION_ID`）。另在 HubSpot → Settings → Integrations → Email 連結 Gmail，往來自動記錄。

### 3.3 手機聯絡人 → Google 聯絡人
- iPhone：設定 → 聯絡人 → 帳號 → Gmail 開啟「聯絡人」；預設帳號設為 Gmail
- Android：設定 → Google → 聯絡人同步 開啟
- 之後在 Attio 以 CSV 匯入（Google 聯絡人 → 匯出 Google CSV），匯入時新增欄位「來源=個人聯絡人」。不建議全量同步到 HubSpot（行銷工具，誤寄風險高）。

### 3.4 LINE 官方帳號
1. LINE Official Account Manager → 設定 → Messaging API → 啟用，建立 Provider「Symcio」
2. LINE Developers → Messaging API channel：
   - Webhook URL：`https://symcio.tw/api/line/webhook`（symcio repo 分支 `claude/symcio-website-automation-qc2me8` 合併並部署後）
   - 取得 Channel secret、long-lived Channel access token
3. 回應設定：關閉「自動回應訊息」，開啟 Webhook（避免與 bot 重複回覆）
4. Secrets：
   - BrandOS-Infrastructure：`LINE_CHANNEL_ACCESS_TOKEN`；Variables：`LINE_ACCOUNT`（例：@symcio）
   - symcio（Vercel env）：`LINE_CHANNEL_SECRET`、`LINE_CHANNEL_ACCESS_TOKEN`
5. 選單：Actions → LINE Rich Menu Deploy → `dry_run=true` → `false`

### 3.5 Meta（Facebook 粉專 + Instagram）
1. 以 cchuan911@gmail.com 登入 Facebook（個人帳號），在帳號中心把 Cheng0911@hotmail.com、Cheng09112003@yahoo.com.tw 加為聯絡 / 復原信箱
2. business.facebook.com 建立 Business Portfolio「Symcio」，加入 Symcio 粉專；Instagram @symcio.tw 轉為專業帳號並連結粉專
3. developers.facebook.com 建立 App（類型 Business），本人為 App 管理員；
   權限 `pages_read_engagement`、`instagram_basic`、`instagram_manage_insights`（只讀自己的粉專 / IG）
4. Graph API Explorer 取得長效 Page access token
5. Secrets：`META_PAGE_ACCESS_TOKEN`；Variables：`META_PAGE_ID`、`META_IG_USER_ID`
6. Actions → Social Followers Snapshot → `dry_run=true` 確認三平台數字

> symcio repo 分支 `claude/setup-meta-automation-0EqbE` 已有 IG 發文腳本（`ig-automation/`），可沿用同一個 App 與 token。

---

## 四、檔案索引

| 檔案 | 用途 |
|------|------|
| `scripts/attio_sync.py` + `.github/workflows/crm-sync.yml` | Supabase → Attio（每日 03:30）|
| `scripts/social_followers.py` + `.github/workflows/social-followers.yml` | 三平台粉絲快照（每日 10:00）|
| `integrations/line/richmenu.json` / `richmenu.png` | 官方帳號主選單（6 格）|
| `scripts/line_richmenu.py` + `.github/workflows/line-richmenu.yml` | 選單產圖 / 驗證 / 部署 |
| `integrations/line/flex/*.json` + `scripts/line_flex.py` | 健檢結果卡、試用提醒卡 |
| `supabase/migrations/20261106000000_social_followers_attio.sql` | 快照表、`v_social_follower_daily`、sync log 支援 attio |

## 五、外部 API 驗證狀態

開發環境無法連到 LINE / Attio / Meta 網域，以下依各平台 API 規格撰寫，**尚未在線驗證**。首次一律走 dry-run：
- LINE：`/richmenu/validate`、`/message/validate/push` 由官方端點檢查
- Attio：`crm-sync` 先 `limit=1` 實跑
- Meta：`social-followers` dry-run 會印出各平台數字
