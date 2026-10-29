-- ============================================================
-- Member sync + Newsletter consent + LINE OA followers
-- ============================================================
-- 使用端：sall911/symcio（symcio.tw）
--   app/auth/callback            → members.signup_source / newsletter_opt_in、member_sync_log
--   app/api/cron/member-sync     → members.crm_synced_at IS NULL 補同步
--   app/api/cron/weekly-newsletter → newsletter_subscribers.status / invited_at
--   app/api/line/webhook         → line_followers
--
-- 個資法紅線：
--   1. 匯入聯絡人一律 status='pending'，只寄一次確認邀請（invited_at），未確認不得寄週報。
--   2. status='unsubscribed' 僅本人重新訂閱可恢復；自動流程不得改回 active。
--   3. consent_at / consent_source 保存同意證明，供主管機關或當事人查詢。
-- ============================================================

-- ---------- members：同步狀態與來源 ----------
ALTER TABLE members
  ADD COLUMN IF NOT EXISTS signup_source     VARCHAR(40),
  -- signup / google / line / import
  ADD COLUMN IF NOT EXISTS newsletter_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS crm_synced_at     TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_members_crm_unsynced
  ON members(created_at) WHERE crm_synced_at IS NULL;

-- ---------- newsletter_subscribers：同意證明 + double opt-in ----------
ALTER TABLE newsletter_subscribers
  ADD COLUMN IF NOT EXISTS consent_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS consent_source VARCHAR(40),
  -- website / member-signup / member-center / double-opt-in
  ADD COLUMN IF NOT EXISTS invited_at     TIMESTAMPTZ;

-- 既有 active 訂閱者視為已同意（來源為網站表單）
UPDATE newsletter_subscribers
   SET consent_at = COALESCE(consent_at, subscribed_at),
       consent_source = COALESCE(consent_source, source)
 WHERE status = 'active';

ALTER TABLE newsletter_subscribers
  DROP CONSTRAINT IF EXISTS newsletter_subscribers_status_check;
ALTER TABLE newsletter_subscribers
  ADD CONSTRAINT newsletter_subscribers_status_check
  CHECK (status IN ('pending', 'active', 'unsubscribed', 'bounced', 'complained'));

CREATE INDEX IF NOT EXISTS idx_newsletter_subs_pending_uninvited
  ON newsletter_subscribers(created_at) WHERE status = 'pending' AND invited_at IS NULL;

-- ---------- member_sync_log：HubSpot / Notion / Obsidian 每次同步結果 ----------
CREATE TABLE IF NOT EXISTS member_sync_log (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email        VARCHAR(255) NOT NULL,
  member_id    UUID REFERENCES members(id) ON DELETE SET NULL,
  target       VARCHAR(20)  NOT NULL,
  -- hubspot / notion / obsidian
  status       VARCHAR(20)  NOT NULL,
  -- ok / skipped / failed
  external_id  VARCHAR(200),
  error        TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT member_sync_log_target_check CHECK (target IN ('hubspot', 'notion', 'obsidian')),
  CONSTRAINT member_sync_log_status_check CHECK (status IN ('ok', 'skipped', 'failed'))
);

CREATE INDEX IF NOT EXISTS idx_member_sync_log_email ON member_sync_log(email, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_member_sync_log_failed ON member_sync_log(created_at DESC) WHERE status = 'failed';

COMMENT ON TABLE member_sync_log IS 'Append-only log of member fan-out to HubSpot / Notion / Obsidian.';

-- ---------- line_followers：LINE 官方帳號好友 ----------
CREATE TABLE IF NOT EXISTS line_followers (
  line_user_id     VARCHAR(64) PRIMARY KEY,
  display_name     VARCHAR(120),
  picture_url      VARCHAR(500),
  language         VARCHAR(10),
  member_id        UUID REFERENCES members(id) ON DELETE SET NULL,
  -- 預留：LINE Login 綁定會員後填入
  followed_at      TIMESTAMPTZ,
  unfollowed_at    TIMESTAMPTZ,
  last_message_at  TIMESTAMPTZ,
  last_message     VARCHAR(500),
  needs_human      BOOLEAN NOT NULL DEFAULT FALSE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_line_followers_needs_human
  ON line_followers(last_message_at DESC) WHERE needs_human;

DROP TRIGGER IF EXISTS line_followers_updated_at ON line_followers;
CREATE TRIGGER line_followers_updated_at
  BEFORE UPDATE ON line_followers
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

-- ---------- RLS：client 全封鎖，僅 service_role ----------
ALTER TABLE member_sync_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE line_followers  ENABLE ROW LEVEL SECURITY;

-- ---------- members：限制會員可自行修改的欄位 ----------
-- members_self_update 原本允許會員更新自己整列，含 plan / quota / crm_synced_at，
-- 等同可自行升級方案。改為欄位層級授權：只開放個人資料欄位。
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE UPDATE ON members FROM authenticated;
    GRANT UPDATE (display_name, company_name, title, avatar_url, locale) ON members TO authenticated;
  END IF;
END $$;
