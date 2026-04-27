#!/usr/bin/env bash
# scripts/db/apply-migrations.sh
# 把 supabase/migrations/*.sql 推到指定 Supabase project。
#
# WHY:
#   平常透過 GitHub Actions (.github/workflows/supabase-deploy.yml) 推 migration，
#   但需要手動 bootstrap 一個全新 project（如本次 symcio-brandos 缺 25+ 張表）時，
#   用本腳本一次推完所有 migration。
#
# 用法：
#   export SUPABASE_ACCESS_TOKEN=<personal-access-token>
#   export SUPABASE_DB_PASSWORD=<db-password>
#   export SUPABASE_PROJECT_REF=<project-ref>     # 例：friwpqphwumomernsouh
#   ./scripts/db/apply-migrations.sh [--dry-run]
#
# 安全機制：
#   - 預設要求互動式確認（除非加 --yes）
#   - 對 production 應改走 GitHub Actions deploy workflow（有 required reviewers）

set -euo pipefail

DRY_RUN=0
ASSUME_YES=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --yes|-y)  ASSUME_YES=1 ;;
    -h|--help)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "[error] unknown arg: $arg" >&2; exit 1 ;;
  esac
done

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
  echo "[error] supabase CLI not found." >&2
  exit 1
fi

echo "[info] target project ref: $SUPABASE_PROJECT_REF"
echo "[info] migrations to push:"
ls -1 supabase/migrations/

if [[ "$ASSUME_YES" -ne 1 ]]; then
  read -r -p "Push these migrations to $SUPABASE_PROJECT_REF? (type 'yes'): " confirm
  if [[ "$confirm" != "yes" ]]; then
    echo "[abort] confirmation not received."
    exit 1
  fi
fi

echo "[info] linking project"
supabase link --project-ref "$SUPABASE_PROJECT_REF" >/dev/null

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "[dry-run] would run: supabase db push --include-all"
  exit 0
fi

echo "[info] pushing migrations (--include-all)"
supabase db push --include-all

echo "[info] done. verify in Supabase Studio Table Editor."
