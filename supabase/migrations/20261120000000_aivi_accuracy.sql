-- ============================================================
-- AIVI Accuracy — 「AI 有沒有把你講對」事實正確性欄位
-- ============================================================
-- 對應 pipeline：scripts/aivi_tracker.py → scripts/aivi_accuracy.py
--
-- WHY：提及率只量「有沒有講到」，客戶痛點是「講錯」（同名混淆、錯誤主張、
--      講不出可查證事實）。正確性判定為規則式，可稽核、可重現。
-- 紅線：accuracy_method 必須記錄（acc-v1/<facts version>），
--      facts 升版後的正確率不得與舊版直接比較。
-- ============================================================

ALTER TABLE aivi_responses
  ADD COLUMN IF NOT EXISTS run_no SMALLINT DEFAULT 1;   -- 同題同引擎第幾次重複採樣

ALTER TABLE aivi_mentions
  ADD COLUMN IF NOT EXISTS accuracy        VARCHAR(20),     -- correct / partial / wrong / absent
  ADD COLUMN IF NOT EXISTS error_type      VARCHAR(40),     -- wrong_fact / name_collision / no_verifiable_fact
  ADD COLUMN IF NOT EXISTS facts_hit       SMALLINT,        -- 命中幾項可查證事實
  ADD COLUMN IF NOT EXISTS conflicts_found TEXT[] DEFAULT '{}',  -- 命中的錯誤主張 id
  ADD COLUMN IF NOT EXISTS accuracy_method VARCHAR(60);     -- 例：acc-v1/symcio-facts-v1

ALTER TABLE aivi_mentions DROP CONSTRAINT IF EXISTS aivi_mentions_accuracy_chk;
ALTER TABLE aivi_mentions ADD CONSTRAINT aivi_mentions_accuracy_chk
  CHECK (accuracy IS NULL OR accuracy IN ('correct', 'partial', 'wrong', 'absent'));

CREATE INDEX IF NOT EXISTS idx_aivi_mentions_accuracy
  ON aivi_mentions(brand_id, accuracy, created_at DESC);

-- 月報用：每品牌每月正確率（分母 = 有提及且已判定）
CREATE OR REPLACE VIEW v_aivi_accuracy_monthly AS
SELECT
  m.brand_id,
  date_trunc('month', m.created_at)::date              AS period,
  m.accuracy_method,
  COUNT(*) FILTER (WHERE m.accuracy <> 'absent')        AS scored,
  ROUND(100.0 * COUNT(*) FILTER (WHERE m.accuracy = 'correct')
        / NULLIF(COUNT(*) FILTER (WHERE m.accuracy <> 'absent'), 0), 1) AS correct_rate_pct,
  ROUND(100.0 * COUNT(*) FILTER (WHERE m.accuracy = 'wrong')
        / NULLIF(COUNT(*) FILTER (WHERE m.accuracy <> 'absent'), 0), 1) AS wrong_rate_pct,
  COUNT(*) FILTER (WHERE m.error_type = 'name_collision') AS name_collisions,
  COUNT(*) FILTER (WHERE m.error_type = 'wrong_fact')     AS wrong_facts
FROM aivi_mentions m
WHERE m.accuracy IS NOT NULL
GROUP BY 1, 2, 3;
