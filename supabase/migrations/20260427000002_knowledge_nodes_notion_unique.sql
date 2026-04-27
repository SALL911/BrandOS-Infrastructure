-- Partial unique index on knowledge_nodes.source for Notion-sourced rows.
--
-- WHY:
--   Notion → repo → Supabase 單向同步管線需要穩定 ID 才能 idempotent UPSERT。
--   `source = 'notion:<page_id>'` 即為該穩定 ID。
--
-- WHAT:
--   Partial unique index — 只對 'notion:%' 前綴的 source 強制唯一性，
--   不影響其他來源（手工輸入、其他自動匯入）的 source 可重複。
--
-- HOW:
--   `scripts/notion_to_knowledge_nodes.py` 用 `ON CONFLICT (source) WHERE source LIKE 'notion:%'`
--   命中此 index，存在則更新，不存在則插入。

CREATE UNIQUE INDEX IF NOT EXISTS uniq_knowledge_nodes_notion_source
  ON knowledge_nodes (source)
  WHERE source LIKE 'notion:%';

COMMENT ON INDEX uniq_knowledge_nodes_notion_source IS
  'Partial unique on source for Notion sync UPSERT. See scripts/notion_to_knowledge_nodes.py.';
