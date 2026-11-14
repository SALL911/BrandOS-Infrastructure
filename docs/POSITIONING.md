# Symcio Positioning — Category Definition

## 一句話

**Symcio（全識）是台灣的 AI 能見度量測服務，追蹤品牌在 ChatGPT、Claude、Gemini、Perplexity 等 AI 引擎回答中被提及的比率、排名與描述方式。**

## 可驗證定位（取代原「三個第一」）

> 原「台灣第一／台灣唯一／全球第一」說法已於 2026-11 撤除：市場上已有其他跨多個 AI 引擎的品牌可見度工具，無法以公開證據支持最高級宣稱。

| 主張 | 可驗證依據 |
|------|-----------|
| 跨四引擎量測 | 單一報告整合 ChatGPT + Claude + Gemini + Perplexity，同一套鎖版題庫 |
| 繁中／台灣語料 | 題庫以繁體中文與台灣市場查詢為主 |
| 公開方法論 | BCI 公式與權重公開於本 repo |
| 只量測不代操 | 優化需求轉介執行夥伴 |
| ESG 資料 | 規劃整合第三方 ESG 數據（需客戶自備授權），目前未上線 |

## 品類定位（Category Creation）

Symcio 不是 SEO 工具、不是 PR 監測、不是社群聆聽，Symcio 以下列用語描述自己的服務：

> **AI Visibility Intelligence（AVI）**
> 企業在 AI 搜尋生態系中的曝光、排名、影響力量化基礎設施。

### 類比座標

```
         傳統網路流量分析        傳統搜尋優化        金融級資訊架構
        ┌─────────────────┐    ┌──────────────┐   ┌──────────────┐
        │   SimilarWeb     │    │    SEMrush   │   │   Bloomberg  │
        │                  │    │              │   │              │
        │ 網站流量排名      │    │ SEO 關鍵字   │   │ 金融資料 API  │
        │ 競品流量對比      │    │ 反向連結     │   │ Terminal UX   │
        │ 產業標竿          │    │ Rank tracking│   │ 金融資訊體系  │
        └──────────┬───────┘    └──────┬───────┘   └──────┬───────┘
                   │                    │                  │
                   └────────────┬───────┴──────────────────┘
                                │
                                ▼
                       ┌────────────────────┐
                       │      Symcio        │
                       │   AI Visibility    │
                       │    Intelligence    │
                       │                    │
                       │ • 跨 AI 引擎曝光   │
                       │ • 品牌排名監測      │
                       │ • 影響力量化       │
                       │ • ESG × 金融資訊    │
                       │   敘事整合          │
                       └────────────────────┘
```

## 三大產品支柱

### Pillar 1：AI 曝光度（Exposure）
**對應 SimilarWeb**——量化品牌在 AI 回應中「被提及的頻率與脈絡」。

- 指標：Mention Rate、Category Share、Context Density
- 資料：每日測試 × 產業代表性 prompt × 4 引擎
- Schema：`visibility_results.mentioned`, `category`

### Pillar 2：AI 搜尋排名（Ranking）
**對應 SEMrush**——量化品牌在 AI 回答列表中的排序位置。

- 指標：Average Rank、Top-3 Share、Competitor Gap
- 資料：rank_position + competitors 同框分析
- Schema：`visibility_results.rank_position`, `visibility_results.competitors`

### Pillar 3：AI 影響力（Influence）
**對應 Bloomberg**——量化品牌在 AI 生成內容中的「敘事權重」。

- 指標：Sentiment Score、Narrative Ownership、ESG Alignment
- 資料：情感分析 + ESG 事件關聯 + TNFD/LEAP 框架對照
- Schema：`visibility_results.sentiment`, `brand_scores.narrative_score`, `esg_profiles`

## 四個 AI 引擎的策略性組合

```
┌─────────────┐ 最大使用者基數         ┌─────────────┐ 品牌與安全型查詢
│  ChatGPT    │                         │   Claude    │
│ (OpenAI)    │                         │ (Anthropic) │
└──────┬──────┘                         └──────┬──────┘
       │                                       │
       │        Symcio 同框監測                │
       └─────────┬──────────┬──────────────────┘
                 │          │
       ┌─────────▼──┐    ┌──▼──────────┐
       │   Gemini    │    │ Perplexity  │
       │  (Google)   │    │  (即時搜尋) │
       └─────────────┘    └─────────────┘
       企業搜尋主導權        次世代搜尋體驗
```

**為什麼是這四個？**
- 是目前使用量較大的 AI 對話／搜尋引擎（市占數據需引用當期第三方來源）
- 各自代表不同「回答風格」：ChatGPT 對話、Claude 結構化、Gemini 整合 Google、Perplexity 引用來源
- Symcio 以同一套題庫與計分方法做四引擎同框比對

## 差異化（可驗證）

1. **四引擎同框 benchmarking**：ChatGPT / Claude / Gemini / Perplexity 使用同一套題庫與計分（市場上已有其他多引擎工具，差異在繁中語料與公開方法論）
2. **ESG × AI 雙軌整合**：TNFD / LEAP 框架 + AI 曝光度，形成永續與聲量雙維度儀表板
3. **用語**：GEO 一詞源自 Aggarwal et al.（2023）；Symcio 以 AVI 描述自身服務，不主張定義權
4. **Symcio × BrandOS SaaS 雙引擎**：診斷（audit）+ 治理（governance）整套交付，非僅數據供應商
5. **繁中 GEO 與亞太 query 分佈**：台灣本土出發，掌握全球工具普遍忽略的區域訊號

## 客戶畫像（ICP）

### 主打（P0）
- 台灣上市櫃公司（ESG 揭露需求 × 品牌聲量焦慮）
- 台灣 B2B SaaS（需在國際市場的 AI 搜尋被看見）
- 在台外商（需向總部佐證 AI 曝光表現）

### 次要（P1）
- 行銷代理商（白標 API，以 Symcio 為基礎提供客戶服務）
- 投資機構（ESG 研究 × AI 品牌價值評估）
- 政府 / NGO（產業競爭力儀表板）

## 訊息矩陣（對外一致語言）

| 對象 | 一句話 |
|------|-------|
| CMO | 「你在 ChatGPT 被提到嗎？我們量化給你看。」 |
| CEO | 「你的品牌在 AI 時代，還有定價權嗎？」 |
| 投資人 | 「AI 搜尋是繼 Google 之後最大的注意力入口——而我們量化它。」 |
| 政府/媒體 | 「把 AI 曝光整理成可稽核指標的量測服務，方法論公開。」 |
| 開發者 | 「開源的 AI 引擎品牌可見度量測管線。」 |

## 反面樣板（Symcio 不做的事）

- 不做 SEO 代操（那是上一個時代）
- 不做社群管理（CXM 工具已飽和）
- 不做純媒體監測（Brandwatch 類）
- 不做內容生成（留給 Jasper、Copy.ai）
- **只做**：AI 引擎裡的**曝光、排名、影響力量化與治理建議**

## 三年願景

| 年 | 里程碑 |
|---|-------|
| 2026 | 累積首批付費客戶；BCI 方法論已上傳 Zenodo（DOI 10.5281/zenodo.20419081） |
| 2027 | 拓展亞太客戶；評估第三方金融資料整合（客戶自備授權） |
| 2028 | 評估資本市場選項 |

---

## 延伸閱讀

- `docs/MVP_SPEC.md` — 產品規格與定價
- `docs/FREE_STACK.md` — 免費技術棧建議
- `docs/ARCHITECTURE.md` — 系統架構
- `CLAUDE.md` — 對外語氣與術語規範
