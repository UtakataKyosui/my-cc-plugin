#!/bin/bash
# PreToolUse hook (Bash matcher): gh api reviews 投稿時にフォーマットを検証する
# スキルアクティブ中のみ発火する（pr-review-format スキルのスコープ）

set -uo pipefail

if ! command -v jq &>/dev/null; then
  exit 0
fi

INPUT=$(cat)
COMMAND=$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)

if [ -z "$COMMAND" ]; then
  exit 0
fi

# gh api .../reviews の呼び出しかどうか確認
if ! printf '%s' "$COMMAND" | grep -qE 'gh\s+api\s+.*pulls/[0-9]+/reviews'; then
  exit 0
fi

# Python で詳細検証を実行
if command -v python3 &>/dev/null; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # stderr を直接 hook の stderr に流す（advisory も利用者に届くようにする）
  if ! printf '%s' "$COMMAND" | python3 "${SCRIPT_DIR}/validate_review.py"; then
    exit 2
  fi
  exit 0
fi

# Python が使えない場合: body を正確に抽出できないため advisory のみ
printf '[pr-review-format] python3 が見つかりません。フォーマット検証をスキップします。\n' >&2
printf 'body に「## 適正な実装」「## 修正することが望ましいところ」が含まれているか確認してください。\n' >&2
exit 0
