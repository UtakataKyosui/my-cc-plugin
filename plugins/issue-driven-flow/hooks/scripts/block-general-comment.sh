#!/usr/bin/env bash
# PreToolUse:Bash hook: `gh pr comment` の誤用を advisory ブロックする
#
# PR レビューへの返信は必ず個別スレッド内への投稿 (in_reply_to) を使う。
# `gh pr comment` はスレッドではなく PR 本体に投稿するため、通常は誤用。
#
# 例外: dry_run_report.py が dry-run サマリを投稿する場合は正当な使用。
# 環境変数 AUTO_PR_RESPONDER_DRY_RUN_POST=1 がセットされていれば許可する。
#
# このスクリプトは常に exit 0（ブロックしない）。

set -uo pipefail

# 環境変数経由で dry-run 投稿として明示されている場合はスキップ
if [ "${AUTO_PR_RESPONDER_DRY_RUN_POST:-0}" = "1" ]; then
  exit 0
fi

# 標準入力から Bash コマンドを読む（Claude Code が PreToolUse に渡す）
BASH_CMD="${CLAUDE_TOOL_INPUT:-}"

# `gh pr comment` が含まれているか確認
if echo "$BASH_CMD" | grep -q "gh pr comment"; then
  echo "[auto-pr-responder] WARN: \`gh pr comment\` を検出しました。" >&2
  echo "  PR レビューへの返信には \`gh api -X POST\` + \`in_reply_to\` を使用してください。" >&2
  echo "  例: gh api -X POST repos/OWNER/REPO/pulls/NUM/comments \\" >&2
  echo "        -f body='返信内容' -F in_reply_to=ROOT_COMMENT_ID" >&2
  echo "  dry-run サマリの投稿は dry_run_report.py 経由で行ってください。" >&2
fi

exit 0
