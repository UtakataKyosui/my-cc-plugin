#!/bin/bash
# UserPromptSubmit hook: git / jj の変更ファイルとブランチをプロンプト送信前に注入する。
# 変更がない場合は無出力で終了し、トークンを消費しない。
set -euo pipefail

# 依存コマンド確認
if ! command -v jq &>/dev/null; then
  exit 0
fi

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[ -n "$CWD" ] || exit 0

cd "$CWD" || exit 0

# 環境変数による無効化
[ "${CONTEXT_KEEPER_DISABLE_GIT_INJECT:-}" = "1" ] && exit 0

BRANCH=""
CHANGED=""
STAGED=""
VCS=""

# jj 優先、次いで git にフォールバック
if command -v jj &>/dev/null && jj root &>/dev/null 2>&1; then
  VCS="jj"
  BRANCH=$(jj log --no-graph --limit 1 --template 'bookmarks.map(|b| b.name()).join(", ")' 2>/dev/null || true)
  [ -n "$BRANCH" ] || BRANCH=$(jj log --no-graph --limit 1 --template 'change_id.short()' 2>/dev/null || true)
  CHANGED=$(jj diff --name-only 2>/dev/null | head -10 || true)
elif command -v git &>/dev/null && git rev-parse --is-inside-work-tree &>/dev/null 2>&1; then
  VCS="git"
  BRANCH=$(git branch --show-current 2>/dev/null || true)
  CHANGED=$(git diff --name-only 2>/dev/null | head -10 || true)
  STAGED=$(git diff --cached --name-only 2>/dev/null | head -5 || true)
else
  exit 0
fi

# 変更がなければ注入しない
if [ -z "$CHANGED" ] && [ -z "$STAGED" ]; then
  exit 0
fi

CONTEXT="[git状態 (${VCS})]"$'\n'
[ -n "$BRANCH" ]  && CONTEXT="${CONTEXT}ブランチ: ${BRANCH}"$'\n'
[ -n "$STAGED" ]  && CONTEXT="${CONTEXT}ステージ済み:"$'\n'"${STAGED}"$'\n'
[ -n "$CHANGED" ] && CONTEXT="${CONTEXT}変更中:"$'\n'"${CHANGED}"$'\n'

jq -n --arg ctx "$CONTEXT" '{
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext: $ctx
  }
}'

exit 0
