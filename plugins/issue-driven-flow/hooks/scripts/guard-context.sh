#!/bin/bash
# PreCompact hook: 圧縮前に「圧縮後も残すべき情報」を additionalInstructions として注入する。
# 未コミット変更ファイルと .compaction-notes.md があれば保護指示に含める。
set -euo pipefail

if ! command -v jq &>/dev/null; then
  exit 0
fi

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
TRIGGER=$(echo "$INPUT" | jq -r '.trigger // empty' 2>/dev/null)
[ -n "$CWD" ] || exit 0

cd "$CWD" || exit 0

[ "${CONTEXT_KEEPER_DISABLE_COMPACTION_GUARD:-}" = "1" ] && exit 0

INSTRUCTIONS=""

# 未コミット変更ファイルを保護指示に含める（jj / git 両対応）
UNCOMMITTED=""
if command -v jj &>/dev/null && jj root &>/dev/null 2>&1; then
  UNCOMMITTED=$(jj diff --name-only 2>/dev/null | head -20 || true)
elif command -v git &>/dev/null && git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
  UNCOMMITTED=$(git diff --name-only 2>/dev/null | head -20 || true)
  STAGED=$(git diff --cached --name-only 2>/dev/null | head -10 || true)
  [ -n "$STAGED" ] && UNCOMMITTED="${UNCOMMITTED}${UNCOMMITTED:+$'\n'}${STAGED}"
fi

if [ -n "$UNCOMMITTED" ]; then
  INSTRUCTIONS="${INSTRUCTIONS}・作業中のファイル（未コミット）:"$'\n'"${UNCOMMITTED}"$'\n'
fi

# .compaction-notes.md があれば保護指示に追加
NOTES_FILE="${CWD}/.compaction-notes.md"
if [ -f "$NOTES_FILE" ]; then
  NOTES=$(head -20 "$NOTES_FILE")
  INSTRUCTIONS="${INSTRUCTIONS}・保護メモ (.compaction-notes.md):"$'\n'"${NOTES}"$'\n'
fi

# 自動圧縮の場合は git status スナップショットを保存
if [ "$TRIGGER" = "auto" ]; then
  SNAPSHOT_DIR="${CWD}/.claude/compaction-snapshots"
  mkdir -p "$SNAPSHOT_DIR"
  SNAPSHOT_FILE="${SNAPSHOT_DIR}/$(date +%Y%m%d_%H%M%S)-$$.txt"
  if command -v jj &>/dev/null && jj root &>/dev/null 2>&1; then
    jj status 2>/dev/null > "$SNAPSHOT_FILE" || true
  elif command -v git &>/dev/null && git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
    git status --short 2>/dev/null > "$SNAPSHOT_FILE" || true
  fi
fi

# 保護指示がない場合は何も出力しない
[ -n "$INSTRUCTIONS" ] || exit 0

FULL="[要約時に必ず含めること]"$'\n'"${INSTRUCTIONS}"

jq -n --arg instr "$FULL" '{
  hookSpecificOutput: {
    hookEventName: "PreCompact",
    additionalInstructions: $instr
  }
}'

exit 0
