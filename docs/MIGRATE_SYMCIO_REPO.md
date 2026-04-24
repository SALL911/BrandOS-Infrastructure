# symcio.tw 遷移到 `SALL911/symcio` repo × Vercel × Cloudflare

本文是 `scripts/migrate-to-symcio.sh` 的配套操作手冊，處理三件事：

1. 把 `web/landing/` 抽成獨立 repo `SALL911/symcio`
2. 在 Vercel 重新部署、綁 `symcio.tw`
3. 切換 Cloudflare DNS，從 Lovable 原點（`3.33.251.168` / `15.197.225.128`）指到 Vercel，**修掉 Error 525**

> **Error 525 現況**：Cloudflare DNS 的 A record 指到 Lovable，但 Lovable 那端 TLS 已失效（可能配置移除或憑證過期）。無論 code 放哪個 repo，只要 Cloudflare DNS 不改，525 就不會好。本流程的第三階段才是真正修 525 的關鍵。

---

## 一、前置檢查（3 分鐘）

- [ ] 登入 `SALL911` GitHub 帳號
- [ ] 登入 Vercel（用 GitHub SSO）
- [ ] 登入 Cloudflare（`Cchuan911@gmail.com`）
- [ ] 手邊有 Supabase URL / service_role key
- [ ] 手邊有 Stripe / Resend / Composio / Gemini 的 API key（視啟用的 feature）

---

## 二、Phase 1 — 抽 repo（10 分鐘）

### 2.1 跑遷移 script

在 `BrandOS-Infrastructure` repo 根目錄：

```bash
bash scripts/migrate-to-symcio.sh ~/projects/symcio
```

這會：
- 複製 `web/landing/*` → `~/projects/symcio/`（排除 `node_modules` / `.next` / `.env*`）
- 複製 `llms.txt` → `public/llms.txt`
- 複製 `benchmark/ai-brand-visibility-index/` → repo 根（開源方法論）
- 生成公開 `README.md`
- `git init` + 第一筆 commit

### 2.2 在 GitHub 建空 repo

1. https://github.com/new
2. Repository name：**symcio**（全小寫）
3. Owner：**SALL911**
4. Public
5. **不要勾** Add README / Add .gitignore / Choose license（script 已經產好）
6. Create repository

### 2.3 推上去

```bash
cd ~/projects/symcio
git remote add origin https://github.com/SALL911/symcio.git
git push -u origin main
```

驗收：https://github.com/SALL911/symcio 看得到 code。

---

## 三、Phase 2 — Vercel 部署新 repo（10 分鐘）

### 3.1 匯入 repo

1. https://vercel.com/new
2. Import Git Repository → 選 `SALL911/symcio`
3. Configure Project：
   - **Framework Preset**：Next.js（自動偵測）
   - **Root Directory**：`.`（根目錄，**不是** `web/landing`——這點跟舊 setup 不同）
   - Build Command：`npm run build`（預設）
   - Install Command：`npm install`（預設）

### 3.2 環境變數（Production + Preview 都勾）

從舊的 BrandOS-Infrastructure Vercel project 複製，或照 `docs/DOMAIN_DEPLOY.md:62-68` 填：

| Key | 必填 | 說明 |
|-----|------|------|
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | service_role key（server only）|
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ | 同上，給 client |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ | anon key |
| `STRIPE_SECRET_KEY` | 視用 | Stripe server |
| `STRIPE_WEBHOOK_SECRET` | 視用 | Stripe webhook 簽章 |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | 視用 | Stripe client |
| `RESEND_API_KEY` | 視用 | 報告寄信 |
| `GH_DISPATCH_TOKEN` | 視用 | 觸發 geo-audit workflow |
| `COMPOSIO_API_KEY` | 視用 | HubSpot / Gmail 整合 |
| `GOOGLE_GENERATIVE_AI_API_KEY` | 視用 | Gemini agent |

> ⚠️ **不要**把 key 寫進 repo。一律用 Vercel env vars。

### 3.3 Deploy

點 Deploy，等 1-2 分鐘。拿到 `symcio-xxx.vercel.app` 預覽網址。

驗收：
- [ ] `https://symcio-xxx.vercel.app/` 開得起來
- [ ] `https://symcio-xxx.vercel.app/llms.txt` 回 200
- [ ] `/api/scan` 之類的 API route 不是 404

---

## 四、Phase 3 — 切換 domain（**真正修 525** · 20 分鐘）

### 4.1 從 Lovable 解除 symcio.tw 綁定

1. 登入 Lovable → Project Settings → Custom Domain
2. 移除 `symcio.tw` 綁定
3. 這一步避免 Lovable 那端殘留舊的 TLS 配置

### 4.2 在新 Vercel project 加 domain

1. Vercel Dashboard → `symcio` project → Settings → Domains
2. Add：`symcio.tw`（主要）
3. Add：`www.symcio.tw`（設為 Redirect to `symcio.tw`，Permanent 308）
4. Vercel 會顯示需要的 DNS：
   ```
   Type: A     Name: @     Value: 76.76.21.21
   Type: CNAME Name: www   Value: cname.vercel-dns.com
   ```
5. 此時狀態應該是 **Invalid Configuration**（DNS 還沒改到），正常

### 4.3 Cloudflare DNS：刪舊加新

Cloudflare Dashboard → `symcio.tw` → DNS → 記錄：

**刪除**：
- [ ] A `symcio.tw` → `3.33.251.168`（Lovable）
- [ ] A `symcio.tw` → `15.197.225.128`（Lovable）

**新增**（**Proxy status 一定要灰雲 / DNS only**）：

| Type | Name | Content | Proxy |
|------|------|---------|-------|
| A | `@` | `76.76.21.21` | 🌫️ DNS only（灰雲）|
| CNAME | `www` | `cname.vercel-dns.com` | 🌫️ DNS only（灰雲）|

**保留不動**：
- MX × 5（Google Workspace）
- TXT `_dmarc` / SPF / google-site-verification
- CNAME `_domainconnect`（GoDaddy 殘留，不影響；想清可清）

### 4.4 等 Vercel 驗證 + 核發憑證（5-15 分鐘）

Vercel → Domains → `symcio.tw` 狀態應該依序變：

1. Invalid Configuration → Checking → **Valid Configuration**
2. SSL：Pending → Issuing → **Certificate Issued**

若 10 分鐘還沒變 Valid：
- 確認 Cloudflare 的雲是**灰**的（橘雲會擋 Let's Encrypt HTTP-01 驗證）
- `dig symcio.tw A +short` 應回 `76.76.21.21`

### 4.5 驗證 HTTPS

```bash
# 憑證（應該看到 Let's Encrypt issuer、CN=symcio.tw）
echo | openssl s_client -servername symcio.tw -connect symcio.tw:443 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates

# HTTP 應該 200
curl -I https://symcio.tw

# llms.txt / robots.txt / sitemap
curl -sI https://symcio.tw/llms.txt
curl -sI https://symcio.tw/robots.txt
curl -sI https://symcio.tw/sitemap.xml
```

**此時 Error 525 應該消失。** 瀏覽器打開 https://symcio.tw 看到 Symcio landing page。

### 4.6（可選）切回橘雲享受 Cloudflare CDN

憑證穩定後 1-2 小時：

1. Cloudflare → SSL/TLS → Overview → **Full (strict)**（必須，**不要** Flexible）
2. Cloudflare → DNS → A `@` 和 CNAME `www` 從灰雲改**橘雲**
3. Cloudflare → Rules → Page Rules：`http://symcio.tw/*` → Always Use HTTPS
4. 再跑一次 4.5 的 curl 驗證

---

## 五、Phase 4 — 清理舊 setup（10 分鐘）

- [ ] 舊的 Vercel project（`BrandOS-Infrastructure` root + `web/landing`）→ Settings → Domains → **移除** `symcio.tw` 綁定（避免搶 DNS）
- [ ] 舊 Vercel project 改名加 `-deprecated` 或直接刪
- [ ] `BrandOS-Infrastructure` repo 的 `web/landing/` 不急著刪，保留 1-2 週確認新站穩定後再 `git rm -r web/landing/` 並更新 `CLAUDE.md` 第七節目錄

---

## 六、常見問題

### Q1：Vercel 的 free plan 可以綁 symcio.tw 嗎？
可以。Vercel Hobby 允許無限 custom domain，只是不能商用——Symcio 正式營運後要升 Pro（$20/月/seat）。

### Q2：遷移後舊的 `/api/*` 網址還有人在呼叫怎麼辦？
新 repo 的 API 路徑**不變**（還是 `/api/scan` 等），只要 DNS 切過去，所有呼叫自動指到新 Vercel。Stripe webhook / Typeform webhook 如果 URL 硬編碼了舊的 `*.vercel.app`，要去那邊後台更新。

### Q3：benchmark/ai-brand-visibility-index/ 為什麼要跟著搬？
開源方法論放在公開 repo 才有 SEO 價值（GitHub 本身的 PageRank）。放在 infra monorepo 裡沒人會找到。

### Q4：可以不要拆 repo，只修 DNS 嗎？
可以。只做 **Phase 3** 就能修好 525。拆 repo 是為了長期乾淨（public marketing site 不該放在 infra repo），不是為了修 525。

---

## 七、延伸閱讀

- `docs/DOMAIN_DEPLOY.md` — Cloudflare × Vercel 原始部署指南（含 Error 525 runbook）
- `scripts/migrate-to-symcio.sh` — 遷移 script 本身
- `CLAUDE.md` 第九節 — 工具分工 SSoT 規範
