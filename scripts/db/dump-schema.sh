#!/usr/bin/env bash
# scripts/db/dump-schema.sh
# 從線上 Supabase project 反向匯出 schema 至 supabase/snapshots/
#
# WHY:
#   `database/schema.md` 是設計 SSoT，但線上實際狀態（含手動建立的表）
#   可能與 repo migration 不一致。本腳本固化線上現況，做為 reconcile 依據。
#
# 用法：
#   export SUPABASE_ACCESS_TOKEN=<personal-access-token>
#   export SUPABASE_DB_PASSWORD=<db-password>
#   export SUPABASE_PROJECT_REF=<project-ref>     # 例：friwpqphwumomernsouh
#   ./scripts/db/dump-schema.sh
#
# 產物：
#   supabase/snapshots/<UTC-timestamp>_live_schema.sql
#
# 注意：
#   - 不寫入 .env、不在 stdout 印出 secrets
#   - snapshots/ 入 git，但若內容含敏感欄位（policy 含 hardcoded uid 等）需人工 review

set -euo pipefail

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "[error] missing env: $name" >&2
    exit 1
  fi
}

require_env SUPABASE_ACCESS_TOKEN
require_env SUPABASE_DB_PASSWORD
require_env SUPABASE_PROJECT_REF

if ! command -v supabase >/dev/null 2>&1; then
  echo "[error] supabase CLI not found. Install: https://supabase.com/docs/guides/local-development/cli/getting-started" >&2
  exit 1
fi

SNAPSHOT_DIR="supabase/snapshots"
mkdir -p "$SNAPSHOT_DIR"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$SNAPSHOT_DIR/${TS}_live_schema.sql"

echo "[info] linking project $SUPABASE_PROJECT_REF"
supabase link --project-ref "$SUPABASE_PROJECT_REF" >/dev/null

echo "[info] dumping schema to $OUT"
supabase db dump --schema public --file "$OUT"

echo "[info] dump complete:"
ls -lh "$OUT"

echo ""
echo "next steps:"
echo "  1. diff against repo migrations:"
echo "       diff <(cat supabase/migrations/*.sql) $OUT"
echo "  2. for live-only tables, create:"
echo "       supabase/migrations/\$(date -u +%Y%m%d%H%M%S)_adopt_live_only_tables.sql"
