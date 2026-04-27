-- Add publishing-state columns to geo_content for the auto-publisher (P3 roadmap).
--
-- WHY:
--   geo_content 目前只有 published_at 一個欄位區分「已發布 / 草稿」，缺：
--   1. 中介狀態 'approved'（人工審完但還沒進到對外渠道）
--   2. URL slug（讓 web/landing 之後做 /geo/<slug> 路由）
--   為了支援 scripts/geo_publisher.py 的 approved → published 自動流轉，補這兩欄。
--
-- WHAT:
--   - status VARCHAR(20)，CHECK 限定 4 個值：'draft'（預設）/ 'approved' / 'published' / 'archived'
--     轉換規則：人工 draft → approved；publisher.py 自動 approved → published；archived 為 soft-delete
--   - slug VARCHAR(255)，nullable（draft 可不填）；partial unique index 確保非 null 全域唯一
--   - 既有 published_at 仍由 publisher 在轉成 'published' 時設值，相容 RLS policy
--
-- HOW:
--   `scripts/geo_publisher.py` 跑：
--     SELECT * FROM geo_content WHERE status='approved' AND slug IS NOT NULL
--     → 渲染 docs/geo-content/<slug>.md（front-matter + content）
--     → UPDATE status='published', published_at=NOW()
--   排程：`.github/workflows/geo-publisher.yml`（daily cron + dispatch）

ALTER TABLE geo_content
  ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft',
  ADD COLUMN IF NOT EXISTS slug   VARCHAR(255);

ALTER TABLE geo_content
  ADD CONSTRAINT geo_content_status_check
  CHECK (status IN ('draft', 'approved', 'published', 'archived'))
  NOT VALID;

ALTER TABLE geo_content VALIDATE CONSTRAINT geo_content_status_check;

CREATE UNIQUE INDEX IF NOT EXISTS uniq_geo_content_slug
  ON geo_content (slug)
  WHERE slug IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_geo_content_status
  ON geo_content (status, published_at DESC);

COMMENT ON COLUMN geo_content.status IS
  'draft (作者編輯中) → approved (人工審完待發) → published (publisher 已發出) | archived (soft-delete)';
COMMENT ON COLUMN geo_content.slug IS
  'URL slug for /geo/<slug> routing. Partial unique where NOT NULL.';
