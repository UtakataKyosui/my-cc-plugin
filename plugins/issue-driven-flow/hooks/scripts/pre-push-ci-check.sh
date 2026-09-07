#!/bin/bash
# PreToolUse hook (Bash matcher): push コマンド検知時に CI 未実行の警告を出力する
# git push のみ対象（jj push は jj-vcs-workflow に委譲）
# 常に exit 0（advisory のみ、ブロッキングしない）
set -uo pipefail

# jq が利用可能か確認
if ! command -v jq &>/dev/null; then
  echo '{}'
  exit 0
fi

COMMAND=$(jq -r '.tool_input.command // empty' 2>/dev/null || echo "")
if [ -z "$COMMAND" ]; then
  echo '{}'
  exit 0
fi

# git push コマンドかどうかを確認（jj git push は除外）
if ! echo "$COMMAND" | grep -qE '(^|\s)git\s+push\b'; then
  echo '{}'
  exit 0
fi

# jj git push は jj-vcs-workflow に委譲
if echo "$COMMAND" | grep -qE '\bjj\s+git\s+push\b'; then
  echo '{}'
  exit 0
fi

# CI チェック実行済みかどうかを一時ファイルで確認
CI_STATE_FILE="${TMPDIR:-/tmp}/pr-workflow-ci-checked-$(basename "$PWD")"

if [ ! -f "$CI_STATE_FILE" ]; then
  echo "[pr-workflow] CI チェックが未実行です。push 前に /pr-workflow:ci-check を実行することを推奨します。" >&2
fi

echo '{}'
exit 0
