# 社群自動發布 × 數位足跡量測

> 以 Symcio 自身品牌作為 BCI 量測的第一個案例。
> BCI 方法論 DOI：https://doi.org/10.5281/zenodo.20419081

---

## 一、WHY

BCI 把品牌在 AI 搜尋的能見度、ESG 合規與品牌價值整合成可查證的數據。要讓「數位聲量」這類無形資產可查證，需要兩件事同時成立：

1. **發言有紀錄**：每一則官方貼文都能回答「誰核准、何時發、發到哪、結果如何」。
2. **足跡有時間序列**：追蹤數、瀏覽、下載、引用等指標以固定來源、固定頻率留存原始數字。

Symcio 先對自己做到這兩件事，後續才能以同一套流程替客戶量測。

---

## 二、WHAT：系統組成

```
geo_content（已發布）
      │  scripts/social_drafter.py（AI 起草，每日）
      ▼
social_posts  status='draft'
      │  人工核准 → status='approved'
      ▼
scripts/social_publisher.py（每小時）──► Bluesky / Threads / Facebook / Instagram / X / LinkedIn / LINE
      │
      ▼
social_post_deliveries（每通路一列，append-only 稽核紀錄）

scripts/social_footprint.py（每日）──► social_metrics（時間序列）
```

| 元件 | 位置 | 排程 |
|------|------|------|
| 資料表 | `supabase/migrations/20261116000000_social_publishing.sql` | — |
| AI 起草 | `scripts/social_drafter.py`、`.github/workflows/social-drafter.yml` | 每日 13:23（台北） |
| 發布 | `scripts/social_publisher.py`、`.github/workflows/social-publisher.yml` | 09:17–21:17 每小時 |
| 足跡量測 | `scripts/social_footprint.py`、`.github/workflows/social-footprint.yml` | 每日 07:41 |
| 網站端追蹤 | `sall911/symcio`：浮動社群連結、Meta Pixel、LINE Tag | 隨 Vercel 部署 |

三條 workflow 手動觸發時預設 dry-run；排程觸發為實際執行。失敗會由 `cron-failure-alert.yml` 開 issue。

### 風險控管設計

- **人工核准閘門**：AI 只產生 `draft`，不會自行對外發布。
- **品牌語氣檢查**：含禁用詞（創新／顛覆／賦能）、感嘆號、或「授權代表／official partner」字樣的貼文，起草時不寫入、發布時退回 `rejected`。
- **來源限定**：AI 起草只改寫已發布的 `geo_content`，提示詞明確禁止新增原文沒有的事實或客戶名稱。
- **不重複發文**：`(post_id, channel)` 成功紀錄有唯一索引；失敗最多重試 3 次。
- **LINE 群發需另外開啟**：需設定 `LINE_BROADCAST_ENABLED=true`，避免誤耗訊息額度。

---

## 三、HOW：上線檢核表

### 3.1 網站端（Vercel → Project Settings → Environment Variables）

| 變數 | 取得位置 | 狀態 |
|------|---------|------|
| `NEXT_PUBLIC_META_PIXEL_ID` | Meta 事件管理工具 → 資料來源 → 新增像素 | 待填 |
| `NEXT_PUBLIC_LINE_TAG_ID` | LINE Ads Manager → 追蹤 (LINE Tag) → 基本碼中的 `tagId` | 待填 |
| `NEXT_PUBLIC_LINE_ADD_FRIEND_URL` | LINE Official Account Manager → 增加好友 → 建立網址（`https://lin.ee/…`） | 待填 |

`NEXT_PUBLIC_*` 在 build 時寫入，填完需重新部署。驗證：`https://www.symcio.tw/api/readiness` 的 `ready.adTracking` 為 `true`；再用 Meta Pixel Helper 與 LINE Tag Helper（Chrome 擴充功能）確認事件。

LINE Tag 自訂事件需先在 LINE Ads Manager 建立同名事件：`Lead`、`Contact`。

### 3.2 發布端（GitHub → Settings → Environments → production）

Variables（非機密）與 Secrets 分開存放。未設定的通路自動略過。

| 通路 | Variables | Secrets | 取得方式與限制 |
|------|-----------|---------|---------------|
| Bluesky | `BLUESKY_HANDLE`=`symcioai.bsky.social` | `BLUESKY_APP_PASSWORD` | Settings → Privacy and security → App passwords。免費、無審核，建議第一個接上。 |
| Threads | `THREADS_USER_ID` | `THREADS_ACCESS_TOKEN` | Meta for Developers 建立 app → 加入 Threads API → 權限 `threads_basic`、`threads_content_publish`。長效權杖 60 天到期，需定期換發。 |
| Facebook | `FB_PAGE_ID`=`61582414050958` | `FB_PAGE_ACCESS_TOKEN` | 權限 `pages_manage_posts`、`pages_read_engagement`。由長效使用者權杖換得的粉專權杖不會到期。App 需切到 Live 模式，貼文才會對一般人可見。 |
| Instagram | `IG_USER_ID` | 同 `FB_PAGE_ACCESS_TOKEN` | IG 需為專業帳號並連結粉專；權限 `instagram_basic`、`instagram_content_publish`。每則必須有 `image_url`（公開 JPEG）。 |
| X | — | `X_API_KEY`、`X_API_SECRET`、`X_ACCESS_TOKEN`、`X_ACCESS_TOKEN_SECRET` | developer.x.com 建立 app，權限 Read and Write。發文額度與費率依 X 當期方案，上線前確認。 |
| LinkedIn | `LINKEDIN_ORG_ID`=`105910896` | `LINKEDIN_ACCESS_TOKEN` | 公司頁發文需 `w_organization_social`，須申請 Community Management API，審核要求已登記的法人實體。權杖 60 天到期。 |
| LINE | `LINE_BROADCAST_ENABLED`=`true` | `LINE_CHANNEL_ACCESS_TOKEN` | Messaging API channel access token。群發每則消耗「好友數」則訊息額度，建議只給每週精選一則指定 `line` 通路。 |
| AI 起草 | `SOCIAL_DRAFTER_MODEL`（選填）、`SOCIAL_LINK_TEMPLATE`（選填） | `ANTHROPIC_API_KEY` | 預設模型 `claude-opus-5-5`。 |
| 足跡 | `YOUTUBE_CHANNEL_ID`、`FOOTPRINT_GITHUB_REPOS`（選填） | `YOUTUBE_API_KEY`、`X_BEARER_TOKEN` | YouTube Data API v3 金鑰於 Google Cloud Console 建立。 |

### 3.3 日常操作

```sql
-- 手動新增一則貼文
INSERT INTO social_posts (title, body_short, body_medium, link_url, tags, channels)
VALUES ('BCI 方法論公開', '…短版…', '…中版…', 'https://symcio.tw/ebook',
        ARRAY['BCI','AVI'], ARRAY['bluesky','threads','facebook','linkedin']);

-- 核准（之後由排程發布）
UPDATE social_posts SET status='approved', approved_by='sall', approved_at=NOW() WHERE id='…';

-- 查詢發布結果
SELECT p.title, d.channel, d.status, d.external_url, d.error
FROM social_post_deliveries d JOIN social_posts p ON p.id = d.post_id
ORDER BY d.created_at DESC LIMIT 20;

-- 足跡趨勢
SELECT captured_on, channel, metric, value FROM social_metrics
WHERE metric = 'followers' ORDER BY captured_on DESC, channel;
```

---

## 四、已知缺口

| 項目 | 說明 | 建議 |
|------|------|------|
| 文章連結 | 線上站（`sall911/symcio`）沒有 `/geo/[slug]` 頁面，該路由只存在於本 repo 的 `web/landing`。起草器會先實測連結，非 200 就改用首頁。 | 把 `/geo/[slug]` 移植到 `symcio` repo，貼文才能導向文章頁。 |
| ECPay／PayPal 購買轉換 | 瀏覽器返回頁不是付款證明，目前只有 Stripe 驗證已付款才送 `Purchase`。 | 在 `/api/ecpay/callback` 以 Meta Conversions API 伺服器端回傳購買事件。 |
| 隱私權政策 | 網站目前無隱私權頁面；載入 Meta Pixel 與 LINE Tag 後，個資法告知義務與兩家廣告平台政策都要求揭露追蹤行為。 | 上線追蹤碼前新增 `/privacy` 頁面，載明使用的追蹤技術與退出方式。 |
| 權杖到期 | Threads、LinkedIn 權杖 60 天到期，GitHub Actions 無法自行更新 secrets。 | 到期會使 workflow 失敗並自動開 issue；收到後手動換發。 |
| Instagram 圖片 | 沒有自動產圖。 | 以 Canva 範本或 `next/og` 產出 JPEG 後填入 `image_url`。 |

---

## 五、可納入量測的其他數位足跡

BCI 的數位聲量構面可分成四類來源，依「可自動化程度」排列：

| 類別 | 足跡 | 指標 | 取得方式 | 狀態 |
|------|------|------|---------|------|
| **學術／方法論** | Zenodo DOI | 瀏覽、下載 | Zenodo API（免金鑰） | 已接 |
| | OpenAlex／Crossref／Google Scholar | 被引用次數 | OpenAlex API（免金鑰） | 建議 |
| **開源／開發者** | GitHub | stars、forks、watchers | GitHub API | 已接 |
| | Hugging Face（資料集、Space） | 下載、likes | HF Hub API | 建議 |
| **自有媒體** | 官網 | 品牌字搜尋量、曝光、點擊 | Search Console API | 建議 |
| | 電子報 | 訂閱數、開信率 | Kit／Resend API | 建議 |
| | YouTube | 訂閱、觀看、影片數 | YouTube Data API | 已接（待建立頻道） |
| | Podcast（Apple／Spotify／SoundOn／Firstory） | 下載、訂閱、評分 | 各平台後台匯出；RSS 集數可自動抓 | 建議 |
| | LINE／Discord／Telegram | 好友／成員數、封鎖率 | 各平台 API | LINE 已接 |
| **社群** | Bluesky／Threads／Facebook／Instagram／X／LinkedIn | 追蹤數、貼文數 | 各平台 API | 已接（待填金鑰） |
| | 貼文互動 | 觸及、互動率、連結點擊 | 各平台 insights API + GA4 UTM | 建議（下一階段） |
| **第三方聲量** | 新聞與部落格提及 | 提及次數、來源權威度 | Google News RSS、GDELT | 建議 |
| | PTT／Dcard／Mobile01 | 提及次數、情緒 | 需爬取或採購輿情服務 | 評估中 |
| | 反向連結 | 參照網域數 | 既有 SEO 工具 | 建議 |
| **實體識別** | Wikidata／Wikipedia | 條目是否存在、sitelinks 數 | Wikidata API（免金鑰） | 建議 |
| | Google 商家檔案 | 評論數、星等 | Business Profile API | 建議（法人登記後） |
| | 商標（TIPO）、LEI | 註冊狀態 | 公開查詢 | 建議（法人登記後） |
| **AI 可見度** | ChatGPT／Claude／Gemini／Perplexity | 提及率、引用來源 | 既有 `geo_audit.py` | 已有 |

新增來源時，在 `scripts/social_footprint.py` 的 `COLLECTORS` 加一個函式即可，資料表不需變更。

Podcast 與 YouTube 對 AI 可見度有額外價值：逐字稿與節目說明是 AI 引擎容易引用的長文本，建議節目上線時同步發布逐字稿到官網並加上 `PodcastEpisode`／`VideoObject` 結構化資料。
