#!/bin/bash
# SessionStart hook: gh my-task で未対応の PR タスクをセッション開始時に通知する。
# gh 未認証・空リストはサイレントスキップ。
# gh my-task 未インストール時はインストール案内を hookSpecificOutput で通知する。
set -uo pipefail

# 前提コマンド確認
command -v gh &>/dev/null || exit 0
command -v jq &>/dev/null || exit 0

# gh auth 確認（未認証はスキップ）
gh auth status &>/dev/null 2>&1 || exit 0

# gh my-task 拡張の存在確認（未インストール時はインストール案内を出して終了）
if ! gh my-task --help &>/dev/null 2>&1; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: "[gh-my-task] gh my-task 拡張が未インストールです。\n  → gh extension install UtakataKyosui/gh-my-task"
    }
  }'
  exit 0
fi

# 無効化フラグ
[ "${GH_MY_TASK_DISABLE_NOTIFY:-}" = "1" ] && exit 0

# タスク一覧取得（失敗時はサイレントスキップ）
TASKS=$(gh my-task -j -R 2>/dev/null) || exit 0
[ -n "$TASKS" ] || exit 0

# 空リストまたは null はスキップ
VALID=$(echo "$TASKS" | jq 'if type == "array" then length else 0 end' 2>/dev/null || echo 0)
[ "${VALID:-0}" -gt 0 ] || exit 0

COUNT=$VALID

# JSON をコンパクトに整形（最大 15 件に絞り妥当な JSON を維持）
COMPACT=$(echo "$TASKS" | jq -c '.[0:15]' 2>/dev/null)

CONTEXT="[gh-my-task] 未対応の PR タスク: ${COUNT} 件
以下の JSON を参照し、優先対応が必要なものを確認してください。

優先度の目安:
  🔴 reviewDecision == CHANGES_REQUESTED → 自分の PR に修正依頼（要対応）
  🟠 isReviewRequested == true → 自分にレビュー依頼が来ている
  🟡 reviewDecision == REVIEW_REQUIRED → 自分の PR がレビュー待ち

コマンドリファレンス:
  rtk gh my-task -j -R        # 全タスク + レビュー状況
  rtk gh my-task prompt <N>   # PR #N のレビュー対応指示を取得
  rtk gh pr view <N>          # PR 詳細

タスク JSON:
${COMPACT}"

jq -n --arg ctx "$CONTEXT" '{
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
