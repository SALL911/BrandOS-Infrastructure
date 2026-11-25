-- =========================================================
-- bot_* 角色權限行為測試（對應 migration 20261105000000_bot_roles.sql）
-- 以 superuser 執行；全部包在交易內，結束 ROLLBACK，不留資料。
-- 任一斷言失敗 → RAISE EXCEPTION → psql ON_ERROR_STOP 非零退出。
-- =========================================================
BEGIN;

-- ---------- 種子資料（superuser）----------
INSERT INTO geo_content (id, title, content, status, slug) VALUES
  ('00000000-0000-0000-0000-0000000000a1', 'approved row', 'x', 'approved',  't-approved'),
  ('00000000-0000-0000-0000-0000000000a2', 'published row', 'x', 'published', 't-published'),
  ('00000000-0000-0000-0000-0000000000a3', 'draft row', 'x', 'draft', 't-draft');
INSERT INTO leads (id, email, status) VALUES ('00000000-0000-0000-0000-0000000000b1', 'lead@example.com', 'new');
INSERT INTO agent_tasks (agent, task_type, status) VALUES
  ('content-operator', 'generation', 'pending'),
  ('growth-operator',  'execution',  'pending');

-- 斷言工具：執行 SQL，預期失敗（權限或 RLS）
CREATE FUNCTION pg_temp.expect_fail(q TEXT, label TEXT) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    EXECUTE q;
  EXCEPTION WHEN insufficient_privilege OR check_violation THEN
    RETURN;
  END;
  RAISE EXCEPTION 'FAIL (should be denied): %', label;
END $$;
CREATE FUNCTION pg_temp.expect_rows(q TEXT, expected BIGINT, label TEXT) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE n BIGINT;
BEGIN
  EXECUTE q INTO n;
  IF n IS DISTINCT FROM expected THEN
    RAISE EXCEPTION 'FAIL %: expected %, got %', label, expected, n;
  END IF;
END $$;
GRANT EXECUTE ON FUNCTION pg_temp.expect_fail(TEXT, TEXT), pg_temp.expect_rows(TEXT, BIGINT, TEXT)
  TO bot_content, bot_growth, bot_director;

-- ---------- bot_content ----------
SET LOCAL ROLE bot_content;
INSERT INTO geo_content (title, content, status, slug) VALUES ('ok', 'x', 'draft', 't-new');
SELECT pg_temp.expect_fail($q$INSERT INTO geo_content (title, content, status) VALUES ('x','x','approved')$q$,
                           'content inserts approved');
SELECT pg_temp.expect_fail($q$UPDATE geo_content SET status='approved' WHERE slug='t-draft'$q$,
                           'content changes status');
SELECT pg_temp.expect_rows($q$WITH u AS (UPDATE geo_content SET content='edited' WHERE slug='t-approved' RETURNING 1)
                              SELECT count(*) FROM u$q$, 0, 'content edits approved row');
SELECT pg_temp.expect_rows($q$WITH u AS (UPDATE geo_content SET content='edited' WHERE slug='t-draft' RETURNING 1)
                              SELECT count(*) FROM u$q$, 1, 'content edits draft row');
SELECT pg_temp.expect_fail($q$DELETE FROM geo_content WHERE slug='t-draft'$q$, 'content deletes');
SELECT pg_temp.expect_fail($q$SELECT count(*) FROM leads$q$, 'content reads leads');
SELECT pg_temp.expect_rows($q$SELECT count(*) FROM agent_tasks$q$, 1, 'content sees only own tasks');
RESET ROLE;

-- ---------- bot_growth ----------
SET LOCAL ROLE bot_growth;
SELECT pg_temp.expect_rows($q$SELECT count(*) FROM geo_content$q$, 1, 'growth sees only published');
SELECT pg_temp.expect_fail($q$SELECT raw_event FROM subscription_events$q$, 'growth reads raw_event');
SELECT pg_temp.expect_rows($q$SELECT count(*) FROM (SELECT id, event_type FROM subscription_events) s$q$, 0,
                           'growth reads subscription_events safe cols');
SELECT pg_temp.expect_rows($q$WITH u AS (UPDATE leads SET status='contacted', notes='draft sent' RETURNING 1)
                              SELECT count(*) FROM u$q$, 1, 'growth updates lead status');
SELECT pg_temp.expect_fail($q$UPDATE leads SET email='x@example.com'$q$, 'growth edits lead email');
SELECT pg_temp.expect_fail($q$DELETE FROM leads$q$, 'growth deletes lead');
SELECT pg_temp.expect_fail($q$INSERT INTO geo_content (title, content) VALUES ('x','x')$q$, 'growth writes content');
SELECT pg_temp.expect_fail($q$SELECT count(*) FROM members$q$, 'growth reads members');
SELECT pg_temp.expect_rows($q$SELECT count(*) FROM agent_tasks$q$, 1, 'growth sees only own tasks');
RESET ROLE;

-- ---------- bot_director ----------
SET LOCAL ROLE bot_director;
INSERT INTO agent_tasks (agent, task_type, status) VALUES ('product-engineer', 'execution', 'pending');
SELECT pg_temp.expect_rows($q$SELECT count(*) FROM agent_tasks$q$, 3, 'director sees all tasks');
INSERT INTO knowledge_nodes (node_type, title, insight) VALUES ('商業模式', 't', 'i');
SELECT pg_temp.expect_fail($q$DELETE FROM agent_tasks$q$, 'director deletes tasks');
SELECT pg_temp.expect_fail($q$UPDATE geo_content SET status='approved'$q$, 'director approves content');
SELECT pg_temp.expect_fail($q$SELECT count(*) FROM leads$q$, 'director reads leads');
RESET ROLE;

SELECT 'bot_roles_test: all assertions passed' AS result;
ROLLBACK;
