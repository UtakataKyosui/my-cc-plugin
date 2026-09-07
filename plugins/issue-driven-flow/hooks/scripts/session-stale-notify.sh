#!/bin/bash
# SessionStart hook: gh poi でマージ済みブランチ数をセッション開始時に通知する。
# gh poi 未インストール時はインストール案内を表示。0 件・未認証はサイレントスキップ。
set -uo pipefail

# 前提コマンド確認
command -v gh &>/dev/null || exit 0
command -v jq &>/dev/null || exit 0

# gh auth 確認（未認証はスキップ）
gh auth status &>/dev/null 2>&1 || exit 0

# git リポジトリ外はスキップ
git rev-parse --git-dir &>/dev/null 2>&1 || exit 0

# 無効化フラグ
[ "${BRANCH_CLEANUP_DISABLE_NOTIFY:-}" = "1" ] && exit 0

# gh poi 拡張の存在確認（未インストール時はインストール案内）
if ! gh poi --help &>/dev/null 2>&1; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: "[branch-cleanup] gh poi 拡張が未インストールです。\n  → gh extension install seachicken/gh-poi\nインストール後、セッション開始時にマージ済みブランチを自動検出します。"
    }
  }'
  exit 0
fi

# gh poi --dry-run でマージ済みブランチを取得（hooks.json の timeout に委譲）
STALE_OUTPUT=$(gh poi --dry-run 2>/dev/null) || exit 0
[ -n "$STALE_OUTPUT" ] || exit 0

# ブランチ数をカウント（"Delete:" で始まる行）
COUNT=$(echo "$STALE_OUTPUT" | grep -c "^Delete:" 2>/dev/null || echo 0)
[ "${COUNT:-0}" -gt 0 ] || exit 0

CONTEXT="[branch-cleanup] マージ済みブランチ: ${COUNT} 件が残っています。
  → /branch-cleanup:cleanup-merged で worktree ごと整理できます。
  → gh poi --dry-run で削除候補を確認できます。"

jq -n --arg ctx "$CONTEXT" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
