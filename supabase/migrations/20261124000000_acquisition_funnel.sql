-- ============================================================
-- AI 自動獲客成交系統 — 名單分級、自動跟進、漏斗事件、廣告花費
-- ============================================================
-- WHY:
--   symcio 站台（/service、/audit）已能收名單，但進件後沒有分級、沒有跟進排程，
--   也沒有可計算轉化率與 ROI 的資料。另外 lib/leads/capture.ts 寫入的歸因欄位
--   （utm_* / fbclid 等）從未以 migration 建立，欄位不存在時整筆 insert 會失敗。
--
-- WHAT:
--   1. leads：補歸因欄位、AI 分級欄位、跟進退訂欄位
--   2. lead_followups：跟進信排程（D0 / D2 / D5）
--   3. funnel_events：站內瀏覽事件（計算訪客數與轉化率）
--   4. ad_spend：每日廣告花費（計算 CPL / ROAS）
--   5. orders：補幣別、金流來源、買家 email
--
-- HOW:
--   全部 ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS，可重複執行。
--   新表一律啟用 RLS 且不建 policy（只有 service_role 可存取，內含個資）。
-- ============================================================

-- ---------- 1. leads ----------
ALTER TABLE leads
  -- 歸因（first-touch），由前端 lib/utm/capture.ts 帶入
  ADD COLUMN IF NOT EXISTS utm_source         VARCHAR(255),
  ADD COLUMN IF NOT EXISTS utm_medium         VARCHAR(255),
  ADD COLUMN IF NOT EXISTS utm_campaign       VARCHAR(255),
  ADD COLUMN IF NOT EXISTS utm_content        VARCHAR(255),
  ADD COLUMN IF NOT EXISTS utm_term           VARCHAR(255),
  ADD COLUMN IF NOT EXISTS referrer           TEXT,
  ADD COLUMN IF NOT EXISTS first_landing_url  TEXT,
  ADD COLUMN IF NOT EXISTS first_touch_at     TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS fbclid             TEXT,
  ADD COLUMN IF NOT EXISTS gclid              TEXT,
  ADD COLUMN IF NOT EXISTS li_fat_id          TEXT,
  -- 進件即時分級（A = 優先聯絡、B = 一般、C = 低意圖）
  ADD COLUMN IF NOT EXISTS grade              VARCHAR(1),
  ADD COLUMN IF NOT EXISTS intent             VARCHAR(50),
  ADD COLUMN IF NOT EXISTS ai_summary         TEXT,
  ADD COLUMN IF NOT EXISTS sales_script       TEXT,
  ADD COLUMN IF NOT EXISTS graded_at          TIMESTAMPTZ,
  -- 跟進信退訂
  ADD COLUMN IF NOT EXISTS followup_opt_out   BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS unsubscribe_token  UUID DEFAULT gen_random_uuid(),
  ADD COLUMN IF NOT EXISTS updated_at         TIMESTAMPTZ DEFAULT NOW();

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'leads_grade_check') THEN
    ALTER TABLE leads ADD CONSTRAINT leads_grade_check CHECK (grade IS NULL OR grade IN ('A', 'B', 'C'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_grade ON leads(grade);
CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_unsubscribe_token ON leads(unsubscribe_token);

COMMENT ON COLUMN leads.grade IS 'A/B/C 進件分級。由 symcio lib/ai/grade.ts 於表單送出時計算；與每日 lead_scorer.py 的 score 並存。';
COMMENT ON COLUMN leads.sales_script IS '內部用的建議成交話術，不對外寄送。';

-- ---------- 2. lead_followups ----------
CREATE TABLE IF NOT EXISTS lead_followups (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  lead_id     UUID NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  step        VARCHAR(10) NOT NULL,           -- d0 / d2 / d5
  due_at      TIMESTAMPTZ NOT NULL,
  status      VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending / sent / skipped / failed
  sent_at     TIMESTAMPTZ,
  error       TEXT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (lead_id, step)
);
CREATE INDEX IF NOT EXISTS idx_lead_followups_due ON lead_followups(status, due_at);
ALTER TABLE lead_followups ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE lead_followups IS 'RLS: service_role only. 跟進信排程，由 symcio /api/cron/followups 每日處理。';

-- ---------- 3. funnel_events ----------
CREATE TABLE IF NOT EXISTS funnel_events (
  id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event       VARCHAR(40) NOT NULL,           -- page_view
  path        VARCHAR(255),
  session_id  VARCHAR(64),                    -- 瀏覽器分頁層級的隨機 ID，非個資
  utm_source  VARCHAR(255),
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_funnel_events_created_at ON funnel_events(created_at DESC);
ALTER TABLE funnel_events ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE funnel_events IS 'RLS: service_role only. 站內瀏覽事件，不存 IP 與 email。';

-- ---------- 4. ad_spend ----------
CREATE TABLE IF NOT EXISTS ad_spend (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  spend_date  DATE NOT NULL,
  channel     VARCHAR(40) NOT NULL DEFAULT 'meta',
  campaign    VARCHAR(255) NOT NULL DEFAULT '',
  amount_twd  DECIMAL(12,2) NOT NULL CHECK (amount_twd >= 0),
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (spend_date, channel, campaign)
);
ALTER TABLE ad_spend ENABLE ROW LEVEL SECURITY;
COMMENT ON TABLE ad_spend IS 'RLS: service_role only. 每日廣告花費（新台幣），目前由後台手動輸入。';

-- ---------- 5. orders ----------
ALTER TABLE orders
  ADD COLUMN IF NOT EXISTS currency        VARCHAR(3),    -- NULL 視為 USD（既有 Stripe 訂單）
  ADD COLUMN IF NOT EXISTS provider        VARCHAR(20),   -- stripe / ecpay / paypal
  ADD COLUMN IF NOT EXISTS customer_email  VARCHAR(255),
  ADD COLUMN IF NOT EXISTS provider_ref    VARCHAR(255);  -- 金流端訂單編號，用來避免重複入帳
CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_provider_ref
  ON orders(provider, provider_ref) WHERE provider_ref IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);

-- ---------- 6. 漏斗每日彙總（供 symcio /admin 看板呼叫） ----------
-- 以台北時間分日。p_usd_twd：orders.currency 為 NULL 或 USD 時換算成新台幣的匯率。
CREATE OR REPLACE FUNCTION acquisition_daily(p_since DATE, p_usd_twd NUMERIC DEFAULT 32)
RETURNS TABLE (
  day           DATE,
  sessions      BIGINT,   -- 不重複訪客（分頁層級 session）
  leads         BIGINT,
  grade_a       BIGINT,
  paid_orders   BIGINT,
  revenue_twd   NUMERIC,
  spend_twd     NUMERIC
)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  WITH days AS (
    SELECT generate_series(p_since, (NOW() AT TIME ZONE 'Asia/Taipei')::date, INTERVAL '1 day')::date AS day
  ),
  v AS (
    SELECT (created_at AT TIME ZONE 'Asia/Taipei')::date AS day, COUNT(DISTINCT session_id) AS n
    FROM funnel_events
    WHERE event = 'page_view' AND created_at >= p_since::timestamp AT TIME ZONE 'Asia/Taipei'
    GROUP BY 1
  ),
  l AS (
    SELECT (created_at AT TIME ZONE 'Asia/Taipei')::date AS day,
           COUNT(*) AS n,
           COUNT(*) FILTER (WHERE grade = 'A') AS a
    FROM leads
    WHERE created_at >= p_since::timestamp AT TIME ZONE 'Asia/Taipei'
    GROUP BY 1
  ),
  o AS (
    SELECT (created_at AT TIME ZONE 'Asia/Taipei')::date AS day,
           COUNT(*) AS n,
           SUM(CASE WHEN COALESCE(currency, 'USD') = 'TWD' THEN price ELSE price * p_usd_twd END) AS rev
    FROM orders
    WHERE payment_status = 'paid' AND created_at >= p_since::timestamp AT TIME ZONE 'Asia/Taipei'
    GROUP BY 1
  ),
  s AS (
    SELECT spend_date AS day, SUM(amount_twd) AS amt
    FROM ad_spend
    WHERE spend_date >= p_since
    GROUP BY 1
  )
  SELECT d.day,
         COALESCE(v.n, 0),
         COALESCE(l.n, 0),
         COALESCE(l.a, 0),
         COALESCE(o.n, 0),
         COALESCE(o.rev, 0),
         COALESCE(s.amt, 0)
  FROM days d
  LEFT JOIN v ON v.day = d.day
  LEFT JOIN l ON l.day = d.day
  LEFT JOIN o ON o.day = d.day
  LEFT JOIN s ON s.day = d.day
  ORDER BY d.day;
$$;

-- 內含營收與名單數，只開放給 service_role
REVOKE ALL ON FUNCTION acquisition_daily(DATE, NUMERIC) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION acquisition_daily(DATE, NUMERIC) TO service_role;
