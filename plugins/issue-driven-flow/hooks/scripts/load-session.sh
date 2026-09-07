#!/bin/bash
# SessionStart hook: 24 時間以内の .claude/session-summary.md を前回セッションの引き継ぎとして注入する。
# サマリが存在しない、または古い場合は何も出力しない。
set -euo pipefail

if ! command -v jq &>/dev/null; then
  exit 0
fi

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[ -n "$CWD" ] || exit 0

[ "${CONTEXT_KEEPER_DISABLE_SESSION_RELAY:-}" = "1" ] && exit 0

SUMMARY="${CWD}/.claude/session-summary.md"

if [ ! -f "$SUMMARY" ]; then
  exit 0
fi

# macOS (stat -f %m) / Linux (stat -c %Y) 両対応
FILE_MTIME=$(stat -f %m "$SUMMARY" 2>/dev/null || stat -c %Y "$SUMMARY" 2>/dev/null || echo 0)
NOW=$(date +%s)
AGE=$(( NOW - FILE_MTIME ))

# 24 時間 (86400 秒) 以内のみ注入
if [ "$AGE" -ge 86400 ]; then
  exit 0
fi

MAX_LINES=${CONTEXT_KEEPER_SESSION_SUMMARY_MAX_LINES:-200}
MAX_BYTES=${CONTEXT_KEEPER_SESSION_SUMMARY_MAX_BYTES:-8192}

CONTENT=$(head -n "$MAX_LINES" "$SUMMARY" | head -c "$MAX_BYTES")
[ -n "$CONTENT" ] || exit 0

FILE_SIZE=$(wc -c < "$SUMMARY" | tr -d '[:space:]')
TRUNCATED_NOTE=""
if [ "$FILE_SIZE" -gt "$MAX_BYTES" ]; then
  TRUNCATED_NOTE=$'\n'"[... session summary truncated to ${MAX_LINES} lines / ${MAX_BYTES} bytes ...]"
fi

CONTEXT="[前回セッションの引き継ぎ]"$'\n'"${CONTENT}${TRUNCATED_NOTE}"

jq -n --arg ctx "$CONTEXT" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'

exit 0
