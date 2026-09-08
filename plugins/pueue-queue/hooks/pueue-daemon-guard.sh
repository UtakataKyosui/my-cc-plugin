#!/bin/bash
# PreToolUse hook: pueue コマンド実行前に pueued デーモンの稼働チェック
# デーモン未起動なら additionalContext で通知（deny はしない）

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // ""' 2>/dev/null)

if [ -z "$COMMAND" ]; then
  exit 0
fi

# pueue コマンドが含まれるか確認（pueued デーモン起動コマンド自体は除外）
if ! echo "$COMMAND" | grep -qE '(^|&&[[:space:]]*|;[[:space:]]*)pueue[[:space:]]'; then
  exit 0
fi

# pueue がインストールされているか確認
if ! command -v pueue >/dev/null 2>&1; then
  exit 0
fi

# pueued デーモンの稼働チェック
if pueue status >/dev/null 2>&1; then
  # デーモン稼働中 → 通常通り実行
  exit 0
fi

# デーモン未起動 → additionalContext で通知（non-blocking）
jq -n \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:"⚠️ Pueue デーモンが起動していません。pueue コマンドを実行する前に `pueued -d` でデーモンを起動してください。または `pueue-queue:pueue-task` スキルを使用するとデーモン確認・起動を自動で行います。"}}'
