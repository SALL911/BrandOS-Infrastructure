-- =========================================================
-- AI 助手專屬資料庫角色（docs/ai-team/README.md §3.1）
-- =========================================================
-- WHY:
--   助手若共用 service_role key 會繞過 RLS，任一助手出錯即可讀寫全庫。
--   每個助手一個 NOLOGIN 群組角色，只授權其職責所需的表 / 欄位 / 列。
--
-- WHAT:
--   bot_director : agent_tasks 讀 / 新增 / 改 status,output；knowledge_nodes、memory_contexts 讀 / 新增；
--                  geo_content、workflow_runs 唯讀
--   bot_content  : geo_content 只能新增 status='draft' 的列、只能改 draft 列的內容欄位（不能改 status）；
--                  news_items、aivi_scores_monthly、bci_snapshots、knowledge_nodes 唯讀
--   bot_growth   : 漏斗相關表唯讀（subscription_events 不含 raw_event）；geo_content 只看 published；
--                  leads 只能改 status / notes
--   三者皆無 DELETE；content / growth 只能讀寫 agent_tasks 中 agent = 自身代號 的列。
--
-- HOW（登入帳號不進 repo）:
--   本 migration 只建群組角色。登入帳號由創辦人在 Supabase SQL Editor 手動建立：
--     CREATE ROLE content_bot LOGIN PASSWORD '<密碼管理器產生>' IN ROLE bot_content;
--   pooler 連線使用者名稱為 content_bot.<project_ref>，存入 GitHub Secret CONTENT_SUPABASE_DB_URL。
--   詳見 docs/ai-team/README.md §3.2。

-- ---------- 1. 群組角色（idempotent；重跑時先收回全部表權限再重新授權）----------
DO $$
DECLARE r TEXT;
BEGIN
  FOREACH r IN ARRAY ARRAY['bot_director', 'bot_content', 'bot_growth'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN NOBYPASSRLS', r);
    END IF;
    EXECUTE format('GRANT USAGE ON SCHEMA public TO %I', r);
    EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', r);
  END LOOP;
END $$;

-- ---------- 2. 表 / 欄位權限 ----------
-- bot_director
GRANT SELECT, INSERT          ON agent_tasks     TO bot_director;
GRANT UPDATE (status, output) ON agent_tasks     TO bot_director;
GRANT SELECT                  ON workflow_runs   TO bot_director;
GRANT SELECT                  ON geo_content     TO bot_director;
GRANT SELECT, INSERT          ON knowledge_nodes TO bot_director;
GRANT SELECT, INSERT          ON memory_contexts TO bot_director;

-- bot_content
GRANT SELECT ON geo_content TO bot_content;
GRANT INSERT (brand_id, content_type, title, slug, content, target_queries, platforms, status)
  ON geo_content TO bot_content;
GRANT UPDATE (content_type, title, slug, content, target_queries, platforms)
  ON geo_content TO bot_content;
GRANT SELECT ON news_items, aivi_scores_monthly, bci_snapshots, knowledge_nodes TO bot_content;

-- bot_growth
GRANT SELECT ON leads, subscriptions, visibility_reports, aivi_billing_plans,
                aivi_scores_monthly, newsletter_subscribers, brands, engagement_signals, geo_content
  TO bot_growth;
GRANT SELECT (id, stripe_event_id, event_type, member_id, stripe_customer_id,
              stripe_subscription_id, status, amount_total, currency, processed_at)
  ON subscription_events TO bot_growth;           -- 不含 raw_event（完整 Stripe payload）
GRANT UPDATE (status, notes) ON leads TO bot_growth;

-- content / growth 回報自己的任務進度
GRANT SELECT, UPDATE (status, output) ON agent_tasks TO bot_content, bot_growth;

-- ---------- 3. RLS policies（表已啟用 RLS；無 policy = 拒絕）----------
-- 唯讀全列
DO $$
DECLARE
  rec RECORD;
BEGIN
  FOR rec IN
    SELECT * FROM (VALUES
      ('bot_director', 'agent_tasks'),
      ('bot_director', 'workflow_runs'),
      ('bot_director', 'geo_content'),
      ('bot_director', 'knowledge_nodes'),
      ('bot_director', 'memory_contexts'),
      ('bot_content',  'geo_content'),
      ('bot_content',  'news_items'),
      ('bot_content',  'aivi_scores_monthly'),
      ('bot_content',  'bci_snapshots'),
      ('bot_content',  'knowledge_nodes'),
      ('bot_growth',   'leads'),
      ('bot_growth',   'subscriptions'),
      ('bot_growth',   'subscription_events'),
      ('bot_growth',   'visibility_reports'),
      ('bot_growth',   'aivi_billing_plans'),
      ('bot_growth',   'aivi_scores_monthly'),
      ('bot_growth',   'newsletter_subscribers'),
      ('bot_growth',   'brands'),
      ('bot_growth',   'engagement_signals')
    ) AS t(role_name, table_name)
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON %I', rec.role_name || '_select', rec.table_name);
    EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO %I USING (true)',
                   rec.role_name || '_select', rec.table_name, rec.role_name);
  END LOOP;
END $$;

-- bot_director：建立 / 更新任務、寫知識節點
DROP POLICY IF EXISTS bot_director_insert ON agent_tasks;
CREATE POLICY bot_director_insert ON agent_tasks FOR INSERT TO bot_director WITH CHECK (true);
DROP POLICY IF EXISTS bot_director_update ON agent_tasks;
CREATE POLICY bot_director_update ON agent_tasks FOR UPDATE TO bot_director USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS bot_director_insert ON knowledge_nodes;
CREATE POLICY bot_director_insert ON knowledge_nodes FOR INSERT TO bot_director WITH CHECK (true);
DROP POLICY IF EXISTS bot_director_insert ON memory_contexts;
CREATE POLICY bot_director_insert ON memory_contexts FOR INSERT TO bot_director WITH CHECK (true);

-- bot_content：只能動 draft
DROP POLICY IF EXISTS bot_content_insert ON geo_content;
CREATE POLICY bot_content_insert ON geo_content FOR INSERT TO bot_content
  WITH CHECK (status = 'draft');
DROP POLICY IF EXISTS bot_content_update ON geo_content;
CREATE POLICY bot_content_update ON geo_content FOR UPDATE TO bot_content
  USING (status = 'draft') WITH CHECK (status = 'draft');

-- bot_growth：geo_content 只看已發布
DROP POLICY IF EXISTS bot_growth_select ON geo_content;
CREATE POLICY bot_growth_select ON geo_content FOR SELECT TO bot_growth
  USING (status = 'published');
DROP POLICY IF EXISTS bot_growth_update ON leads;
CREATE POLICY bot_growth_update ON leads FOR UPDATE TO bot_growth USING (true) WITH CHECK (true);

-- content / growth：agent_tasks 只看、只改自己的列
DROP POLICY IF EXISTS bot_content_own_tasks ON agent_tasks;
CREATE POLICY bot_content_own_tasks ON agent_tasks FOR ALL TO bot_content
  USING (agent = 'content-operator') WITH CHECK (agent = 'content-operator');
DROP POLICY IF EXISTS bot_growth_own_tasks ON agent_tasks;
CREATE POLICY bot_growth_own_tasks ON agent_tasks FOR ALL TO bot_growth
  USING (agent = 'growth-operator') WITH CHECK (agent = 'growth-operator');
