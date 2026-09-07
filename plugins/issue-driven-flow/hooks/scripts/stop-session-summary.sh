#!/usr/bin/env bash
# Stop hook: session-summary.md への書き出しを促す
# 環境変数 ISSUE_DRIVEN_FLOW_STOP_SUMMARY=0 で無効化できる

set -uo pipefail

# デフォルト無効。1 を設定すると有効
ENABLED="${ISSUE_DRIVEN_FLOW_STOP_SUMMARY:-0}"
if [ "$ENABLED" = "0" ]; then
  exit 0
fi

PROMPT="このセッションの決定事項・未完了タスク・次回への申し送りを .claude/session-summary.md に日本語で書き出してください。以下の形式で書いてください:\n\n## 決定事項\n- (このセッションで決めたこと)\n\n## 未完了\n- (着手したが終わっていないこと、ファイルパスや Issue 番号があれば記載)\n\n## 次回やること\n1. (優先順に列挙)\n\nファイルに書き出した後、「session-summary.md を保存しました」とだけ返答してください。"

printf '{"hookSpecificOutput":{"hookEventName":"Stop","additionalContext":"%s"}}' \
  "$(printf '%s' "$PROMPT" | sed 's/"/\\"/g')"
