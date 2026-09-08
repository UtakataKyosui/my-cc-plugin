#!/usr/bin/env bash
# PostToolUseFailure hook (Bash matcher): when a jj command fails, print
# error-specific recovery hints. Non-jj failures return early. NEVER blocks
# (always exit 0) — this is advice, not a gate.
set -uo pipefail

# Skip safely when jq is unavailable.
if ! command -v jq &>/dev/null; then
  exit 0
fi

# Extract the failed command from stdin.
COMMAND=$(jq -r '.tool_input.command // empty' 2>/dev/null || echo "")
if [ -z "$COMMAND" ]; then
  exit 0
fi

# Only advise on jj commands (at start / after a pipe, &&, ;, or subshell).
if ! printf '%s\n' "$COMMAND" | grep -qE '(^|[|&;({[:space:]])jj([[:space:]]|$)'; then
  exit 0
fi

echo "[vcs-workflow] jj コマンドが失敗しました。" >&2

# Per-subcommand diagnosis.
if printf '%s\n' "$COMMAND" | grep -qE '\bjj\s+git\s+push\b'; then
  echo "  push 失敗の主な原因:" >&2
  echo "    - リモートとローカルが diverge している → jj git fetch && jj rebase -d main@origin" >&2
  echo "    - 認証エラー → SSH キーまたは Personal Access Token を確認" >&2
  echo "    - 安全な push には jj safe-push コマンドを使用してください" >&2
elif printf '%s\n' "$COMMAND" | grep -qE '\bjj\s+(rebase|squash|merge)\b'; then
  echo "  コンフリクト発生の可能性があります:" >&2
  echo "    - コンフリクト確認: jj status" >&2
  echo "    - コンフリクト解消: jj resolve" >&2
  echo "    - 変更を元に戻す: jj restore" >&2
elif printf '%s\n' "$COMMAND" | grep -qE '\bjj\s+commit\b'; then
  echo "  コミット失敗の主な原因:" >&2
  echo "    - 作業コピーが空 → jj status で変更を確認" >&2
  echo "    - メッセージの指定方法: jj commit -m 'メッセージ'（インタラクティブモード不可）" >&2
elif printf '%s\n' "$COMMAND" | grep -qE '\bjj\s+workspace\b'; then
  echo "  workspace 操作失敗の主な原因:" >&2
  echo "    - 対象パスが既に存在する → 別パスを指定するか既存ディレクトリを削除" >&2
  echo "    - ワークスペース一覧確認: jj workspace list" >&2
else
  echo "  トラブルシューティング:" >&2
  echo "    - 現在の状態確認: jj status" >&2
  echo "    - 変更履歴確認: jj log --limit 10" >&2
  echo "    - jj ヘルプ: jj help <サブコマンド>" >&2
fi

exit 0
