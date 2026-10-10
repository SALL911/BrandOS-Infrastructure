# Gumroad Starter Kit 上架 Runbook（$39 → $260 升級漏斗）

來源：Google Doc「先從 GUMROAD 開始」（Grok 變現策略落地）。
漏斗：Gumroad $39 Starter Kit → 收據信升級 CTA → Stripe $260（$299 VIP − $39 折抵）→ Calendly 預約 → 48h 交付。

---

## WHY：限制與風險（先讀）

| # | 風險 / 限制 | 處置 |
|---|---|---|
| 1 | Gumroad 公開 API **不支援建立產品與上傳檔案**；Receipt 文案也只能在 UI 設定 | 步驟 2–3 為手動（約 10 分鐘） |
| 2 | 本 repo 為 **public**；付費原始碼放 `private/gumroad-starter-kit/` 且已 gitignore | 原始碼需另存於 **private repo**，否則容器回收後只剩 zip |
| 3 | 「48 小時上線」「14 天支援」是可被追究的服務承諾 | 收據文案已註明起算條件（權限備妥後）；接單前確認產能 |
| 4 | $39 折抵需人工對帳 | Stripe 結帳頁收集 `gumroad_email` 欄位，交付前比對 Gumroad Sales |
| 5 | 退款政策 | Gumroad 數位商品建議設「無退款，除非無法使用」，並在產品描述明示 |
| 6 | 稅務 | Gumroad 自 2025 起為 Merchant of Record，代收代繳銷售稅；Stripe $260 由 Symcio 自行開立發票 |

---

## 步驟 1：建立 $260 升級付款連結（GitHub Actions，2 分鐘）

1. Repo → Settings → Secrets and variables → Actions → 新增 `STRIPE_SECRET_KEY`
   （建議 Stripe Dashboard → Developers → API keys → **Create restricted key**，只開 Products / Prices / Payment Links 寫入）。
2. Actions → **Stripe Upgrade Link** → Run workflow
   - `calendly_url`：VIP 建置預約頁（例 `https://calendly.com/<you>/vip-setup`；留空則顯示 Stripe 確認頁）
   - `amount_usd`：`260`
3. Job summary 顯示 `https://buy.stripe.com/...` → 複製。冪等，可重跑。

本機替代：`STRIPE_SECRET_KEY=sk_... CALENDLY_URL=https://... python scripts/stripe_upgrade_link.py`

**零 Stripe 替代**：在 Gumroad 另建一個 $260 產品「VIP Concierge Full Setup — Upgrade」，以其產品頁網址作為升級連結。

---

## 步驟 2：打包 zip

```bash
scripts/build_gumroad_kit.sh                       # README 指向收據信內的升級連結（建議：換連結不需重打包）
UPGRADE_URL=https://buy.stripe.com/xxx scripts/build_gumroad_kit.sh   # 或直接嵌入 README
```
輸出：`dist/gumroad/nextjs-claude-hubspot-starter-v1.0.0.zip`、`dist/gumroad/README.md`。
腳本會：排除 `node_modules` / `.env*`、掃描真實金鑰、`npm ci` + typecheck + build 驗證後才出包。

---

## 步驟 3：Gumroad 上架（約 10 分鐘）

1. gumroad.com → **New product** → 類型 **Digital product**
   - Name：`Next.js + Claude Code + HubSpot Automation Starter Kit`
   - Price：**$39**
2. **Product page**
   - URL / permalink：`claude-hubspot-starter`
   - Description：貼上 `dist/gumroad/README.md` 的「產品簡介」「內容」「定價與權益方案」三段
   - Cover：1280×720；Thumbnail：600×600
   - Summary（購買按鈕旁）：`Deploy a Claude-powered lead pipeline into HubSpot on Vercel in 5 minutes.`
3. **Content** 分頁 → Upload files：`nextjs-claude-hubspot-starter-v1.0.0.zip`、`README.md`
4. **Receipt** 分頁（Edit product → Receipt / Custom receipt text）：貼上下方「收據信文案」，替換 `<UPGRADE_URL>`
5. Settings → Advanced → **Ping**（選填）：`https://<kit-deploy-domain>/api/gumroad/ping?secret=<GUMROAD_PING_SECRET>` → Gumroad 銷售自動寫入 HubSpot
6. **Publish** → 用 100% off 折扣碼自購一次，確認：收到 zip、收據含升級連結、連結開啟 $260 Stripe 結帳。

---

## 收據信文案（Gumroad Receipt，貼上即用）

```
【中文】
恭喜！你的 Starter Kit 原始碼與環境配置檔已可下載。

身為創業者，你最昂貴的成本不是代碼，而是時間。自行配置 Vercel、排查 CORS 與除錯 HubSpot Webhook，通常需要 3 到 8 小時。

VIP 專人建置升級：你剛付的 $39 已全額折抵，只需補差額 $260。資深工程師遠端連線，替你完成 Vercel 部署、自訂網域與 HubSpot 雙向名單串接並實機測試。正式環境於建置時段開始、權限備妥後 48 小時內上線，並附 14 天 Telegram / LINE 支援。

👉 以 $260 差額升級：<UPGRADE_URL>
（結帳時請填寫你在 Gumroad 使用的 email，以便折抵對帳）

【EN】
Your starter kit and config files are ready to download.

Your time is your highest-leverage asset. Wiring up API permissions, CORS rules and HubSpot webhooks typically takes 3–8 hours.

VIP upgrade: your $39 is 100% credited toward the $299 Full Setup — pay only the $260 balance. We handle the Vercel deployment, custom domain and HubSpot workflow end-to-end, live within 48 hours of your setup session (once access is granted), plus 14 days of direct messaging support.

👉 Upgrade for $260: <UPGRADE_URL>
(Enter the email you used on Gumroad at checkout so we can apply your credit.)
```

---

## 步驟 4：交付 SOP（收到 $260 後）

1. Stripe Payments → 核對 `gumroad_email` 與 Gumroad Sales 是否有 $39 紀錄（無紀錄 → 補收 $39 或退款）。
2. 確認 Calendly 預約；建置前索取：GitHub / Vercel 協作者邀請、HubSpot Super Admin、DNS 權限。
3. 依 kit `README.md` 部署 → 綁網域 → `docs/HUBSPOT_SETUP.md` 串 pipeline → 送測試名單驗證。
4. 交付紀錄寫入 HubSpot deal（stage = closed won），並依 CLAUDE.md §五 存一筆 `knowledge_nodes`（節點類型：商業模式）。

## 追蹤指標

| 指標 | 計算 | 目標 |
|---|---|---|
| Gumroad 轉換率 | Sales ÷ Views | ≥ 2% |
| 升級率 | Stripe $260 筆數 ÷ Gumroad $39 筆數 | ≥ 10% |
| 平均客單 | 總營收 ÷ 不重複買家 | ≥ $65 |

## 原始碼保存

`private/gumroad-starter-kit/` 不進本 public repo。建立 private repo 保存：
```bash
cd private/gumroad-starter-kit && git init && git add . && git commit -m "starter kit v1.0.0"
git remote add origin git@github.com:SALL911/starter-kit-private.git && git push -u origin main
```
