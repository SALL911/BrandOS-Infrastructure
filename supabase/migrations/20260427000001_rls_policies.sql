-- ============================================================
-- RLS Policies — explicit posture for Layer 1-7
-- ============================================================
-- 對應文件：docs/SCHEMA_AUDIT.md §RLS
--
-- 設計：
--   1. 預設 deny（RLS enabled + 無 policy = 只有 service_role 可存取）
--   2. 公開讀取需明確 policy（如 knowledge_nodes.is_public=true）
--   3. 會員自有資料政策已在 20260422000001_members_audit_history.sql 處理
--   4. ai_queries / ai_responses 在 initial schema 漏 enable，本 migration 補上
-- ============================================================

-- ---------- 補 RLS：initial schema 遺漏的兩張表 ----------
ALTER TABLE ai_queries   ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_responses ENABLE ROW LEVEL SECURITY;

-- ---------- 公開讀：is_public=true 的知識節點 ----------
-- knowledge_nodes 已有 is_public 欄位（default false）。
-- 行銷頁 / 內容站可拉公開節點作為「品類洞察」展示。
DROP POLICY IF EXISTS knowledge_nodes_public_read ON knowledge_nodes;
CREATE POLICY knowledge_nodes_public_read ON knowledge_nodes
  FOR SELECT
  USING (is_public = TRUE);

-- ---------- 公開讀：geo_content（已發布且非草稿） ----------
-- geo_content 是要餵給 ChatGPT/Perplexity 的對外答案內容；
-- 已 published_at 非 NULL 視為對外可見。
DROP POLICY IF EXISTS geo_content_public_read ON geo_content;
CREATE POLICY geo_content_public_read ON geo_content
  FOR SELECT
  USING (published_at IS NOT NULL);

-- ---------- 公開讀：visibility_reports（客戶最終報告） ----------
-- 報告 PDF 走 storage signed URL；DB 層的 metadata 設為對外可讀，
-- 真正的存取控制在 Storage bucket policy。
-- 若日後要做「會員自家報告才看得到」，再改為 owner-based。
DROP POLICY IF EXISTS visibility_reports_public_read ON visibility_reports;
CREATE POLICY visibility_reports_public_read ON visibility_reports
  FOR SELECT
  USING (TRUE);

-- ---------- 其餘表：service_role only（不加 policy = default deny） ----------
-- 以下表已 RLS enabled 但無 policy，意即只有 service_role 可存取。
-- 這是正確姿態，本 migration 僅以 COMMENT 明示意圖。
COMMENT ON TABLE brands             IS 'RLS: service_role only. Customer brand records are confidential.';
COMMENT ON TABLE brand_scores       IS 'RLS: service_role only.';
COMMENT ON TABLE esg_profiles       IS 'RLS: service_role only. Sensitive ESG metrics.';
COMMENT ON TABLE esg_events         IS 'RLS: service_role only.';
COMMENT ON TABLE visibility_results IS 'RLS: service_role only. Aggregated via visibility_reports for public.';
COMMENT ON TABLE memory_contexts    IS 'RLS: service_role only. Internal Symcio session memory.';
COMMENT ON TABLE training_data      IS 'RLS: service_role only.';
COMMENT ON TABLE feedback_loops     IS 'RLS: service_role only.';
COMMENT ON TABLE workflow_runs      IS 'RLS: service_role only.';
COMMENT ON TABLE agent_tasks        IS 'RLS: service_role only.';
COMMENT ON TABLE subscriptions      IS 'RLS: service_role only. Member-facing data goes through members table.';
COMMENT ON TABLE orders             IS 'RLS: service_role only.';
COMMENT ON TABLE leads              IS 'RLS: service_role only. PII inside.';
COMMENT ON TABLE brand_projects     IS 'RLS: service_role only.';
COMMENT ON TABLE ai_queries         IS 'RLS: service_role only. Standardized prompt library.';
COMMENT ON TABLE ai_responses       IS 'RLS: service_role only. Raw AI engine outputs.';

COMMENT ON POLICY knowledge_nodes_public_read   ON knowledge_nodes
  IS 'Anyone can read knowledge nodes flagged is_public=true. Used by symcio.tw content pages.';
COMMENT ON POLICY geo_content_public_read       ON geo_content
  IS 'Published GEO content is publicly readable. Used to surface answer-engine content externally.';
COMMENT ON POLICY visibility_reports_public_read ON visibility_reports
  IS 'Report metadata is public; PDF access controlled via Storage signed URLs.';
