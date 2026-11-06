-- =========================================================
-- 社群粉絲每日快照 + Attio 同步紀錄
-- =========================================================
-- WHY:
--   1. 追蹤 LINE 官方帳號、Facebook 粉專、Instagram 粉絲數的每日變化，
--      作為 SaaS 漏斗頂端指標（scripts/social_followers.py 每日寫入）。
--   2. CRM 改為 Supabase → HubSpot + Attio 單向扇出；Attio 同步結果
--      記錄在既有 member_sync_log，需放寬 target 限制。
--
-- WHAT:
--   social_follower_snapshots：每平台每帳號每日一列（重跑覆蓋當日）
--   member_sync_log.target 增加 'attio'

-- ---------- 1. 粉絲快照 ----------
CREATE TABLE IF NOT EXISTS social_follower_snapshots (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  platform      VARCHAR(20)  NOT NULL,
  -- line / facebook / instagram
  account       VARCHAR(120) NOT NULL,
  -- LINE bot basic id / FB page id / IG user id
  snapshot_date DATE         NOT NULL,
  followers     INTEGER,
  extra         JSONB,
  -- LINE: targetedReaches / blocks；FB: fan_count 等平台附加欄位
  created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT social_follower_snapshots_platform_check
    CHECK (platform IN ('line', 'facebook', 'instagram')),
  CONSTRAINT social_follower_snapshots_unique UNIQUE (platform, account, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_social_follower_snapshots_trend
  ON social_follower_snapshots (platform, account, snapshot_date DESC);

ALTER TABLE social_follower_snapshots ENABLE ROW LEVEL SECURITY;
-- 無 client policy：僅 service_role / bot 角色經授權存取

-- 日變化檢視：昨日對比
CREATE OR REPLACE VIEW v_social_follower_daily
  WITH (security_invoker = true) AS
SELECT platform, account, snapshot_date, followers,
       followers - LAG(followers) OVER (PARTITION BY platform, account ORDER BY snapshot_date) AS delta
FROM social_follower_snapshots;

-- 增長官可讀粉絲趨勢（bot_roles migration 已建立角色）
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bot_growth') THEN
    GRANT SELECT ON social_follower_snapshots, v_social_follower_daily TO bot_growth;
    DROP POLICY IF EXISTS bot_growth_select ON social_follower_snapshots;
    CREATE POLICY bot_growth_select ON social_follower_snapshots FOR SELECT TO bot_growth USING (true);
  END IF;
END $$;

-- ---------- 2. member_sync_log 支援 attio ----------
ALTER TABLE member_sync_log DROP CONSTRAINT IF EXISTS member_sync_log_target_check;
ALTER TABLE member_sync_log
  ADD CONSTRAINT member_sync_log_target_check
  CHECK (target IN ('hubspot', 'notion', 'obsidian', 'attio'));
