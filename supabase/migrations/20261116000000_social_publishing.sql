-- =========================================================
-- 社群自動發布與數位足跡量測
-- =========================================================
-- WHY
--   Symcio 以自身品牌作為 BCI 量測的第一個案例：社群發布需要可稽核的佇列
--   （誰核准、何時發、每個通路的結果），社群足跡需要每日快照才能形成時間序列。
-- WHAT
--   social_posts            待發布內容佇列（draft → approved → published）
--   social_post_deliveries  每則貼文在每個通路的發布結果（append-only）
--   social_metrics          每日社群／學術／開源足跡快照
-- HOW
--   scripts/social_drafter.py   由 geo_content 產生 draft（AI 起草）
--   scripts/social_publisher.py 發布 approved 貼文
--   scripts/social_footprint.py 寫入 social_metrics

-- ---------- social_posts：發布佇列 ----------
CREATE TABLE IF NOT EXISTS social_posts (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title         VARCHAR(300) NOT NULL,
  body_short    TEXT NOT NULL,
  -- 短版：X / Bluesky / Threads 使用，含連結需 ≤ 280 字元
  body_medium   TEXT,
  -- 中版：Facebook / LinkedIn / Instagram / LINE 使用；NULL 時退回 body_short
  link_url      VARCHAR(1000),
  image_url     VARCHAR(1000),
  -- Instagram 必填（公開可抓取的 JPEG 網址）
  tags          TEXT[] NOT NULL DEFAULT '{}',
  channels      TEXT[] NOT NULL,
  status        VARCHAR(20) NOT NULL DEFAULT 'draft',
  scheduled_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  source        VARCHAR(30) NOT NULL DEFAULT 'manual',
  source_id     UUID,
  -- source='geo_content' 時為 geo_content.id，避免同一篇重複起草
  approved_by   VARCHAR(120),
  approved_at   TIMESTAMPTZ,
  published_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT social_posts_status_check
    CHECK (status IN ('draft', 'approved', 'partial', 'published', 'failed', 'rejected')),
  CONSTRAINT social_posts_source_check
    CHECK (source IN ('manual', 'geo_content', 'news', 'ai')),
  CONSTRAINT social_posts_channels_check
    CHECK (channels <@ ARRAY['bluesky','threads','facebook','instagram','x','linkedin','line']::TEXT[]
           AND cardinality(channels) > 0)
);

CREATE INDEX IF NOT EXISTS idx_social_posts_due
  ON social_posts(scheduled_at) WHERE status IN ('approved', 'partial');
CREATE UNIQUE INDEX IF NOT EXISTS uq_social_posts_source
  ON social_posts(source, source_id) WHERE source_id IS NOT NULL;

DROP TRIGGER IF EXISTS social_posts_updated_at ON social_posts;
CREATE TRIGGER social_posts_updated_at
  BEFORE UPDATE ON social_posts
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

COMMENT ON TABLE social_posts IS '社群發布佇列。status=approved 且 scheduled_at 到期者由 social_publisher 發布。';

-- ---------- social_post_deliveries：各通路發布結果 ----------
CREATE TABLE IF NOT EXISTS social_post_deliveries (
  id            BIGSERIAL PRIMARY KEY,
  post_id       UUID NOT NULL REFERENCES social_posts(id) ON DELETE CASCADE,
  channel       VARCHAR(20) NOT NULL,
  status        VARCHAR(10) NOT NULL,
  external_id   VARCHAR(300),
  external_url  VARCHAR(1000),
  error         VARCHAR(1000),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT social_post_deliveries_status_check CHECK (status IN ('ok', 'failed', 'skipped'))
);

-- 同一貼文同一通路只會成功一次：重跑不會重複發文
CREATE UNIQUE INDEX IF NOT EXISTS uq_social_post_deliveries_ok
  ON social_post_deliveries(post_id, channel) WHERE status = 'ok';
CREATE INDEX IF NOT EXISTS idx_social_post_deliveries_post
  ON social_post_deliveries(post_id, created_at DESC);

COMMENT ON TABLE social_post_deliveries IS 'Append-only：每次發布嘗試一列，作為對外發言的稽核紀錄。';

-- ---------- social_metrics：數位足跡每日快照 ----------
CREATE TABLE IF NOT EXISTS social_metrics (
  id           BIGSERIAL PRIMARY KEY,
  captured_on  DATE NOT NULL DEFAULT CURRENT_DATE,
  channel      VARCHAR(30) NOT NULL,
  -- bluesky / threads / facebook / instagram / x / linkedin / line / youtube / github / zenodo …
  account      VARCHAR(200) NOT NULL,
  metric       VARCHAR(60) NOT NULL,
  -- followers / posts / views / downloads / stars / citations …
  value        NUMERIC NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_social_metrics_day UNIQUE (captured_on, channel, account, metric)
);

CREATE INDEX IF NOT EXISTS idx_social_metrics_series
  ON social_metrics(channel, metric, captured_on DESC);

COMMENT ON TABLE social_metrics IS '品牌數位足跡時間序列（每日一筆），供 BCI 數位聲量構面查證。';

-- ---------- RLS：client 全封鎖，僅 service_role ----------
ALTER TABLE social_posts           ENABLE ROW LEVEL SECURITY;
ALTER TABLE social_post_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE social_metrics         ENABLE ROW LEVEL SECURITY;
