#!/usr/bin/env bash
# SubagentStart hook: PR レビュー修正エージェント起動前チェック
# - gh CLI の認証確認
# - VCS (jj / git) の状態確認

set -euo pipefail

result="{}"

# gh CLI の認証確認
if command -v gh &>/dev/null; then
  if ! gh auth status &>/dev/null 2>&1; then
    echo "[auto-pr-responder] WARN: gh CLI が認証されていません。PR レビュー取得に失敗する可能性があります。" >&2
  fi
fi

# VCS 状態確認（jj または git）
if command -v jj &>/dev/null && jj root &>/dev/null 2>&1; then
  # jj リポジトリ
  if jj status 2>/dev/null | grep -q "^Working copy changes:"; then
    echo "[auto-pr-responder] INFO: jj リポジトリ — 作業コピーに変更があります。" >&2
  fi
elif command -v git &>/dev/null; then
  # git リポジトリ（失敗しても abort しない）
  if [ "$(git rev-parse --git-dir 2>/dev/null || true)" != "" ]; then
    if ! (git diff --quiet 2>/dev/null || true) || ! (git diff --cached --quiet 2>/dev/null || true); then
      echo "[auto-pr-responder] INFO: git リポジトリ — ステージングされていない変更があります。" >&2
    fi
  fi
fi

echo "$result"
