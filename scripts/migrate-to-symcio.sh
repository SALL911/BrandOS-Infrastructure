#!/usr/bin/env bash
# Symcio 網站遷移 script
# 把 BrandOS-Infrastructure/web/landing/ 抽出成獨立 symcio repo
#
# Usage:
#   bash scripts/migrate-to-symcio.sh [TARGET_DIR]
#
# Default target: ~/projects/symcio
#
# 這個 script 做的事：
#   1. 驗證 source repo 結構完整
#   2. 用 rsync 複製 web/landing/* 到 TARGET（排除 node_modules / .next / .env.local）
#   3. 從 repo 根複製 llms.txt → TARGET/public/llms.txt（讓 AI 可 fetch）
#   4. 複製 benchmark/ai-brand-visibility-index/ 過去（開源方法論）
#   5. 產生 symcio 公開 repo 的 README.md
#   6. git init + 第一筆 commit + 設定 main branch
#   7. 印出下一步的 GitHub / Vercel / DNS 指令
#
# 不會做的事：
#   - 不會自動推到 GitHub（你要先在 github.com/new 建好 repo 再 push）
#   - 不會碰你的 BrandOS-Infrastructure repo（純讀）
#   - 不會複製 node_modules / .next（省空間）

set -euo pipefail

# ---------- 參數 ----------
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-$HOME/projects/symcio}"

echo "=================================================="
echo " Symcio migration"
echo "=================================================="
echo "  Source  : $SOURCE_DIR"
echo "  Target  : $TARGET_DIR"
echo ""

# ---------- 前置檢查 ----------
if [[ ! -d "$SOURCE_DIR/web/landing" ]]; then
  echo "✗ source 不是 BrandOS-Infrastructure：找不到 web/landing/"
  echo "  請在 BrandOS-Infrastructure repo 根目錄執行此 script。"
  exit 1
fi

if [[ ! -f "$SOURCE_DIR/web/landing/package.json" ]]; then
  echo "✗ web/landing/package.json 不存在，source 可能已經損毀"
  exit 1
fi

if [[ -e "$TARGET_DIR" && -n "$(ls -A "$TARGET_DIR" 2>/dev/null || true)" ]]; then
  echo "⚠  target 已存在且非空：$TARGET_DIR"
  read -r -p "    這會覆蓋現有內容，確定繼續？ [y/N] " yn
  [[ "$yn" == "y" || "$yn" == "Y" ]] || { echo "取消。"; exit 1; }
fi

command -v tar >/dev/null || { echo "✗ tar 未安裝"; exit 1; }
command -v git >/dev/null || { echo "✗ git 未安裝"; exit 1; }

mkdir -p "$TARGET_DIR"
echo "✓ target 目錄就緒"
echo ""

# ---------- 1. 複製 web/landing 內容（用 tar 管道，排除大檔）----------
echo "[1/5] 複製 web/landing/ 到 target（排除 node_modules / .next / .env*）"
tar -cf - \
  --exclude='node_modules' \
  --exclude='.next' \
  --exclude='.vercel' \
  --exclude='*.tsbuildinfo' \
  --exclude='.env' \
  --exclude='.env.local' \
  --exclude='.env.*.local' \
  -C "$SOURCE_DIR/web/landing" . \
  | tar -xf - -C "$TARGET_DIR"
echo "   ✓ 完成"

# ---------- 2. llms.txt → public/ ----------
echo "[2/5] 複製 llms.txt → public/llms.txt（讓 AI crawler 讀 symcio.tw/llms.txt）"
if [[ -f "$SOURCE_DIR/llms.txt" ]]; then
  mkdir -p "$TARGET_DIR/public"
  cp "$SOURCE_DIR/llms.txt" "$TARGET_DIR/public/llms.txt"
  echo "   ✓ 完成"
else
  echo "   ⚠  source 找不到 llms.txt，略過"
fi

# ---------- 3. 開源 ABVI 方法論 ----------
echo "[3/5] 複製 benchmark/ai-brand-visibility-index/ 到 target root"
if [[ -d "$SOURCE_DIR/benchmark/ai-brand-visibility-index" ]]; then
  mkdir -p "$TARGET_DIR/ai-brand-visibility-index"
  tar -cf - -C "$SOURCE_DIR/benchmark/ai-brand-visibility-index" . \
    | tar -xf - -C "$TARGET_DIR/ai-brand-visibility-index"
  echo "   ✓ 完成（方法論、schema、demo 一起過去）"
else
  echo "   ⚠  source 找不到 benchmark/ai-brand-visibility-index/，略過"
fi

# ---------- 4. 產生公開 repo 的 README.md ----------
echo "[4/5] 產生 symcio repo 的公開 README.md"
cat > "$TARGET_DIR/README.md" <<'README_EOF'
# Symcio — AI Visibility Intelligence

**Symcio is the AI-era SimilarWeb + SEMrush + Bloomberg: a platform that quantifies enterprise brand exposure, ranking, and influence across generative AI engines (ChatGPT, Claude, Gemini, Perplexity).**

- **Category**: AI Visibility Intelligence (AVI) — a category Symcio defines.
- **Headquarters**: Taiwan.
- **Website**: https://symcio.tw
- **Wikidata**: [Q138922082](https://www.wikidata.org/wiki/Q138922082)
- **Discord**: https://discord.gg/jGWJr2Sd

## What Symcio is

Symcio is **Taiwan's first platform for quantifiable AI brand exposure**, **Taiwan's only cross-engine brand-visibility index**, and **the world's first AI-search ranking intelligence platform**. Symcio measures brand presence inside generative AI answers — a distinct category from web search.

What SimilarWeb did for web traffic, Symcio does for AI answers.
What SEMrush did for Google rankings, Symcio does for ChatGPT rankings.
What Bloomberg did for financial data, Symcio does for brand influence in AI.

## Open-source methodology

The **AI Brand Visibility Index (ABVI)** methodology is published at [`ai-brand-visibility-index/`](./ai-brand-visibility-index/) — scoring formula, test prompt protocol, and reference Python implementation.

## Repository structure

```
symcio/
├── app/                           # Next.js 14 App Router pages
│   ├── page.tsx                   # Homepage
│   ├── about/                     # About Symcio
│   ├── pricing/                   # Pricing plans
│   ├── tools/
│   │   ├── brand-check/           # Free Scan form
│   │   └── entity-builder/        # GEO Entity Builder
│   ├── api/
│   │   ├── agent/                 # Free Scan agent (Supabase + Composio + Gemini)
│   │   ├── checkout/              # Stripe checkout session
│   │   └── webhooks/stripe/       # Stripe webhook handler
│   └── layout.tsx                 # Organization Schema + GA4 + HubSpot
├── components/                    # Shared React components
├── lib/                           # Server-side integrations (Stripe, Supabase, Resend, GitHub dispatch)
├── public/
│   ├── faq/                       # Static FAQ knowledge base (5 audiences × 10 Q&A, FAQPage Schema)
│   ├── llms.txt                   # AI-readable canonical summary
│   ├── robots.txt                 # AI crawler policy (GPTBot / ClaudeBot / etc. allowed)
│   └── sitemap.xml
├── ai-brand-visibility-index/     # ABVI open-source methodology (MIT)
└── README.md
```

## Tech stack

- Next.js 14 (App Router) + TypeScript strict
- Tailwind CSS (dark theme `#0a0a0a` + brand `#c8f55a`)
- Inter + DM Mono (Google Fonts)
- Supabase (PostgreSQL) for leads / visibility data
- Stripe Checkout for $299 Audit / $1,999 Optimization
- Composio for Notion / Gmail automation
- Deployed on Vercel

## Local development

```bash
npm install
cp .env.example .env.local   # fill in Supabase keys
npm run dev                   # http://localhost:3000
```

## Contact

- General: hello@symcio.tw
- Sales: sales@symcio.tw
- Security: security@symcio.tw

## License

MIT. See open-source methodology at [`ai-brand-visibility-index/README.md`](./ai-brand-visibility-index/README.md).

---

*Symcio is an AI Visibility Intelligence platform based in Taiwan, quantifying brand presence across ChatGPT, Claude, Gemini, and Perplexity.*
README_EOF

echo "   ✓ 公開 README 產生完成"

# ---------- 5. 初始化 git ----------
echo "[5/5] git init + 第一筆 commit"
cd "$TARGET_DIR"
if [[ -d ".git" ]]; then
  echo "   ⚠  .git 已存在，略過 init"
else
  git init -q
  echo "   ✓ git init"
fi

# 若沒有 global git config，設定 local 佔位值，讓 commit 能跑
if ! git config user.email >/dev/null 2>&1; then
  git config user.email "symcio-migration@local"
  git config user.name  "Symcio Migration"
  echo "   ⚠  沒偵測到 git global config，已設定 local 佔位 user.email / user.name"
fi

git add .
git commit -q -m "Initial commit: Symcio website

Migrated from SALL911/BrandOS-Infrastructure (web/landing/).

Stack: Next.js 14 App Router + TypeScript + Tailwind + Supabase.
Includes: homepage, /about, /pricing, /tools/brand-check,
/tools/entity-builder, /api/agent, /api/checkout,
Stripe webhook, GA4 tracking, Organization Schema,
HubSpot embed, FAQ knowledge base (5 audiences × 10 Q&A),
ABVI open-source methodology.

Brand: #c8f55a lime on #0a0a0a dark theme.
Fonts: Inter + DM Mono (Google Fonts)."

git branch -M main 2>/dev/null || true

if git rev-parse HEAD >/dev/null 2>&1; then
  echo "   ✓ commit: $(git log -1 --oneline)"
else
  echo "   ✗ commit 失敗，請手動檢查 git status"
  exit 1
fi

echo ""
echo "=================================================="
echo " ✅ 遷移完成"
echo "=================================================="
echo ""
echo " TARGET：$TARGET_DIR"
echo ""
echo "下一步（依序做）："
echo ""
echo " 1. 在 GitHub 建新 repo（不要勾任何 initialization）："
echo "    → https://github.com/new"
echo "    → Repository name: symcio"
echo "    → Public"
echo "    → Create repository"
echo ""
echo " 2. 推上 GitHub："
echo "    cd \"$TARGET_DIR\""
echo "    git remote add origin https://github.com/SALL911/symcio.git"
echo "    git push -u origin main"
echo ""
echo " 3. Vercel 匯入 SALL911/symcio："
echo "    → https://vercel.com/new"
echo "    → Import SALL911/symcio"
echo "    → Root Directory: .（根目錄，不是 web/landing）"
echo "    → 加 Environment Variables（見 docs/DOMAIN_DEPLOY.md）"
echo "    → Deploy"
echo ""
echo " 4. 從 Lovable 解除 symcio.tw 綁定"
echo ""
echo " 5. Vercel 新 project → Settings → Domains → 加 symcio.tw"
echo ""
echo " 6. Cloudflare DNS 改指向 Vercel（Proxy 先設灰雲）"
echo ""
echo "=================================================="
