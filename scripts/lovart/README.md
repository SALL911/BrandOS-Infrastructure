# Symcio BrandOS × Lovart 品牌系統自動化

## WHY
依 `docs/DESIGN_SYSTEM.md`（深色款）把 Symcio／BrandOS 的識別系統一次在 Lovart 建成可重跑的專案，讓之後的 AIVI 報告封面、LinkedIn 素材、提案簡報都從同一套規範生成。

## WHAT
| 檔案 | 用途 |
|---|---|
| `brandos_brief.json` | 品牌核心、色彩字體 token、紅線、8 個生成步驟。改這份就能重跑 |
| `run_pipeline.py` | 依序呼叫 Lovart，可續跑，遇到高成本確認會停下 |
| `agent_skill.py` | Lovart 官方 client（github.com/lovartai/lovart-skill，MIT，只用 Python 標準函式庫） |
| `out/manifest.json` | project_id、thread_id、每步產出與 failures |

## HOW
```bash
# 0. 一次性：Lovart 網頁 → 頭像選單 → AK/SK 管理
export LOVART_ACCESS_KEY=ak_xxx
export LOVART_SECRET_KEY=sk_xxx

# 1. 先看 prompt（不扣點）
python3 run_pipeline.py --dry-run

# 2. 跑 01–04（識別系統，thinking mode）→ 人工審 logo
python3 run_pipeline.py --only 01_strategy
python3 run_pipeline.py --only 02_logo
python3 run_pipeline.py --only 03_sub_brand
python3 run_pipeline.py --only 04_spec_sheet

# 3. 在 Lovart 網頁 Brand Kit 面板：上傳選定的 logo、填色票與字體 → 複製 kit ID
#    填入 brandos_brief.json 的 brand_kit_id

# 4. 跑應用物 05–08（fast mode，自動帶 02/04 產出當參考）
python3 run_pipeline.py

# 單步重做：刪掉 manifest 裡該步，或用 --only
```

## 限制
- Brand Kit 不能用 API 建立，只能引用 ID → 步驟 3 必須手動。
- Reasoning mode 在 thread 第一則訊息鎖定：master thread = thinking、apps thread = fast。
- 限流：生成 60 次/分、600 次/時；同一 thread 一次只能跑一個任務。
- `final_status = done` 不代表有圖，看 manifest 的 `generation_succeeded` 和 `failures`。
- 生成的 logo 不能直接拿去申請商標：AI 生成圖的著作權歸屬與近似性需 黃意森律師 確認，選定後建議由設計師向量化重繪。
- AK/SK 只放環境變數或 `.env.local`，不要進 repo。
