#!/usr/bin/env bash
# Link the repo's Symcio voice profile to the path the /ig-* skills read.
# Run once per machine / cloud session: bash scripts/install-ig-voice.sh
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HOME/.claude/instagram"
ln -sf "$repo_root/.claude/instagram/voice.md" "$HOME/.claude/instagram/voice.md"
echo "linked: $HOME/.claude/instagram/voice.md -> $repo_root/.claude/instagram/voice.md"
