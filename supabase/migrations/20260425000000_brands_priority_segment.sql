-- Brand segment + priority 讓 GEO audit queue 能按商業價值排序掃描
-- WHY：symcio 客戶獲客 A/B 要能優先跑某個名單（例如 2026 新創 meta 名單），
-- 現況 queue 是 FIFO（created_at ASC）→ 歷史名單匯入後新 lead 會被擠到後面。
-- 加 priority 後：brands.priority DESC，created_at ASC 作 tie-breaker。

ALTER TABLE brands
  ADD COLUMN IF NOT EXISTS segment_tags JSONB       DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS priority     SMALLINT    DEFAULT 0,
  ADD COLUMN IF NOT EXISTS imported_at  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS source_list  VARCHAR(100);     -- 例：'startup-meta-2026'

-- 讓 queue 撈「等掃 + 按優先序」O(log n)：priority DESC, last_scanned_at ASC NULLS FIRST
CREATE INDEX IF NOT EXISTS idx_brands_priority_scan
  ON brands(priority DESC, last_scanned_at NULLS FIRST)
  WHERE status = 'prospect';

CREATE INDEX IF NOT EXISTS idx_brands_segment_tags
  ON brands USING GIN (segment_tags);

CREATE INDEX IF NOT EXISTS idx_brands_source_list
  ON brands(source_list)
  WHERE source_list IS NOT NULL;
