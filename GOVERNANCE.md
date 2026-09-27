# GOVERNANCE.md — Symcio DAO-lite 治理規則
## v1.0 | 生效日：2026-09-27 | 適用範圍：`SALL911/BrandOS-Infrastructure`、`sall911/symcio`

---

## 一、WHY：為什麼是 DAO-lite

Symcio 的產出同時來自人類成員與 AI agents（Claude Code、Composio workflows、GitHub Actions）。決策若只存在於對話與訊息中，會出現三個問題：

1. **不可追溯**：無法回答「這個 schema / 定價 / 對外宣稱是誰、何時、依據什麼決定的」。
2. **AI 越權風險**：agent 能寫 code、發內容、動資料，但沒有明確的權限邊界。
3. **擴張瓶頸**：新成員、外部貢獻者、合作夥伴加入時，沒有可複製的決策流程。

DAO-lite 取 DAO 的三個元素——**提案公開、投票留痕、規則即程式碼**——但**不採用代幣、鏈上投票或去中心化法律結構**。GitHub 是投票與紀錄的唯一場所（SSoT）。

---

## 二、法律邊界（優先於本文件所有條款）

| 項目 | 規則 |
|------|------|
| 法律主體 | Symcio 之法律權責依公司法由公司負責人／董事會承擔。本文件為**內部作業規範**，不構成合夥、合資、社團或任何獨立法律實體。 |
| 無代幣 | 不發行任何 token、點數、NFT 或可轉讓權益。投票權**不具財產價值**，不得轉讓、交易或兌換。避免落入《證券交易法》有價證券或集資認定。 |
| 無分潤權 | 參與治理不產生股權、分紅、薪資請求權或僱傭關係。報酬一律另以書面契約約定。 |
| 個資與保密 | 任何投票結果不得凌駕《個人資料保護法》、客戶 NDA、或 CLAUDE.md 第六節禁止事項。違反者提案自動無效。 |
| 公開資訊 | 對外文宣涉及 SimilarWeb / SEMrush / Bloomberg 等第三方名稱，依 CLAUDE.md「品牌使用規範」，投票不得核准任何暗示授權或合作的用語。 |

**衝突處理**：本文件 < 法令 < 公司章程／書面契約。發生衝突時以位階高者為準，並由 Steward 於 7 日內提出修正案。

---

## 三、角色（WHO）

| 角色 | 定義 | 投票權 | 合併權 | 目前成員 |
|------|------|-------|-------|---------|
| **Steward** | 公司負責人，最終法律責任人 | 1 票 + 保留否決權（見第五節） | 全部 | @SALL911 |
| **Maintainer** | 對特定模組負責，列於 `.github/CODEOWNERS` | 1 票 | 所負責路徑 | （空缺，由 T2 提案任命） |
| **Contributor** | 過去 90 日內有 ≥1 個已合併 PR 的人類貢獻者 | 諮詢票（計入討論、不計入門檻） | 無 | — |
| **AI Agent** | Claude Code、GitHub Actions、Composio、任何自動化帳號 | **無** | **無** | — |

### 3.1 AI Agent 權限規則（不可由投票放寬，僅能由 T3 修改）

1. Agent 只能**開 PR 或開 proposal issue**，不得合併、不得 approve、不得投票。
2. Agent 的 commit 必須帶可追溯 trailer（如 `Claude-Session:` 或 workflow run URL）。
3. Agent 不得修改本文件、`.github/CODEOWNERS`、`.github/workflows/*` 中的權限區塊（`permissions:`、`secrets.*` 引用）後自行觸發執行；此類 PR 必須人類合併。
4. Agent 產出的對外內容（`geo_content`、landing、新聞稿）一律須人類核准後才進入 `approved` 狀態。
5. Agent 提出的建議與人類提案同權審查，但不計為任何人的票。

### 3.2 成員異動

- 任命／移除 Maintainer：T2 提案。
- 90 日無活動的 Maintainer 自動轉為 Contributor（由 Steward 於季度檢視時執行並記錄於決策日誌）。
- 違反保密或第二節法律邊界：Steward 可立即暫停權限，事後 7 日內以 T2 補正。

---

## 四、決策分級（WHAT）

| 等級 | 範圍 | 流程 | 通過門檻 | 最短公開期 |
|------|------|------|---------|-----------|
| **T0 例行** | 文案修正、bug fix、docs、非 schema 的內部重構、依賴小版本升級 | 一般 PR | 1 位 CODEOWNER approve | 無 |
| **T1 標準** | Supabase migration、新增／修改 workflow、新 agent、對外頁面上線、新增第三方整合、BCI 參數以外的指標邏輯 | PR + 描述中標註 `governance: T1` | 1 位 CODEOWNER approve，且 CI 全綠；Maintainer ≥2 人時需 2 位 | 48 小時 |
| **T2 重大** | 定價、方案結構、品牌定位與對外宣稱、BCI 方法論與權重、資料保留與隱私政策、任命／移除 Maintainer、新增 repo、年度路線圖 | Proposal issue（SIP）→ 投票 → 實作 PR | 有效票 ≥ 2/3 贊成，且投票率 ≥ 50% 有投票權者；Steward 未行使否決 | 7 日 |
| **T3 憲章** | 修改本文件、第 3.1 節 AI 權限、第二節法律邊界、Steward 否決權範圍 | SIP → 投票 → Steward 簽核 | T2 門檻 + Steward 明示同意 | 14 日 |
| **E 緊急** | 資安事件、憑證外洩、客戶資料外洩、服務中斷、法遵命令 | 任一 Maintainer 或 Steward 直接處置 | 事後補正 | 事後 72 小時內補 SIP |

**分級爭議**：無法判斷時，往上一級處理。任何有投票權者可在 PR 留言 `/escalate T2` 要求升級，Steward 裁定。

---

## 五、否決權與制衡

Steward 否決權**僅限**下列事由，行使時必須在 issue 留下書面理由：

1. 違反第二節法律邊界或既有契約義務。
2. 造成公司財務負擔超過當期核准預算。
3. 涉及客戶資料或 ESG 數據混用（CLAUDE.md 第六節）。
4. 與公司章程或董事會決議衝突。

**制衡**：
- 否決理由必須引用上列條號，否則否決無效。
- 被否決提案可於 30 日後修改重提一次。
- 否決紀錄全數寫入決策日誌，每季由 Steward 於季度報告揭露次數與事由。

---

## 六、HOW：提案流程（SIP — Symcio Improvement Proposal）

```
[1] 開 issue（模板：Governance Proposal）→ 自動加 label `proposal`
      ↓ 編號 SIP-YYYY-NNN（由 issue 編號決定）
[2] 討論期（T2: 7 日 / T3: 14 日）→ label `proposal:discussion`
      ↓ 提案人可修改內容；每次實質修改重算最短公開期
[3] 投票期（72 小時）→ label `proposal:voting`
      ↓ 有投票權者於 issue 留言，首行僅寫：
        VOTE: YES | NO | ABSTAIN
        理由（選填，NO 票建議填寫）
[4] 計票 → label `proposal:accepted` 或 `proposal:rejected`
      ↓ 以留言最後一次 VOTE 為準；emoji reaction 不計票
[5] 寫入 docs/governance/DECISIONS.md → 開實作 PR 並連結 SIP
[6] 關閉 issue（state_reason: completed / not_planned）
```

### 6.1 計票規則

- **有效票** = YES + NO（ABSTAIN 計入投票率，不計入 2/3 分母）。
- **投票率** = 投票人數 ÷ 當下有投票權者總數。
- 有投票權者僅 1 人（現況）時：Steward 單人決議有效，但**公開期與決策日誌要求不可省略**。
- 提案人可投票。Agent 開的提案由其人類操作者擔任提案人。
- 利益衝突：與提案有直接財務利益者必須聲明並 ABSTAIN。

### 6.2 提案必填欄位

見 `.github/ISSUE_TEMPLATE/governance-proposal.md`：等級、WHY、WHAT、風險與限制、成本、回滾方案、成功指標、到期檢視日。

---

## 七、決策日誌（Decision Log）

- 位置：`docs/governance/DECISIONS.md`（append-only，只增不改）。
- 每筆紀錄：SIP 編號、標題、等級、結果、票數、否決紀錄、實作 PR、檢視日。
- 更正錯誤以新增一筆 `CORRECTION` 紀錄處理，不改寫舊紀錄。
- 重大決策同步寫入 Supabase `knowledge_nodes`（節點類型：商業模式），遵循 CLAUDE.md 第五節格式。

---

## 八、執行面：規則即程式碼

治理規則若只寫在文件裡不會被遵守。以下設定為本文件的強制層：

| 控制點 | 設定 | 狀態 |
|-------|------|------|
| `.github/CODEOWNERS` | 關鍵路徑指定審查人 | 已建立 |
| Issue 模板 | `governance-proposal.md` | 已建立 |
| 決策日誌 | `docs/governance/DECISIONS.md` | 已建立 |
| Branch protection（`main`） | Require PR、Require CODEOWNERS review、Require status checks、禁止 force push、禁止刪除 | **待 Steward 於 GitHub Settings 手動開啟** |
| Labels | `proposal`、`proposal:discussion`、`proposal:voting`、`proposal:accepted`、`proposal:rejected`、`governance:T1` | **待建立** |
| 自動計票 workflow | 投票期結束自動計票並留言結果 | 規劃中（P2） |

---

## 九、檢視與修訂

- 每季第一週由 Steward 檢視：否決次數、T2/T3 提案數、Agent 越權事件、Maintainer 活躍度。
- 本文件修訂一律走 T3；版本號同步更新於檔頭與 CLAUDE.md。

---

## 附錄 A：快速判斷表

| 我要做的事 | 等級 |
|-----------|------|
| 修 landing 錯字 | T0 |
| 新增 Supabase 欄位 | T1 |
| 新增 GitHub Actions cron | T1 |
| 把 geo_content 自動發布從人工核准改成自動 | T3（涉及 3.1 第 4 點） |
| 調整 BCI 權重 FBV / SCV / AIV | T2 |
| 調整方案售價 | T2 |
| API key 外洩需立即輪替 | E |
| 讓 Claude Code 可自行合併 T0 PR | T3 |
