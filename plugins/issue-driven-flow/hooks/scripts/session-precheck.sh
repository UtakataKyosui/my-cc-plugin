#!/usr/bin/env bash
# SessionStart hook: auto-pr-responder の前提条件確認
# gh auth と VCS の状態を確認して警告を出す（exit 0 でブロックしない）

set -uo pipefail

# gh CLI の認証確認
if command -v gh &>/dev/null; then
  if ! gh auth status &>/dev/null 2>&1; then
    echo "[auto-pr-responder] WARN: gh CLI が認証されていません。" >&2
    echo "  → gh auth login を実行してください。" >&2
  fi
fi

# VCS 状態確認（jj または git）
if command -v jj &>/dev/null && jj root &>/dev/null 2>&1; then
  echo "[auto-pr-responder] INFO: jj リポジトリを検出" >&2
elif command -v git &>/dev/null && git rev-parse --git-dir &>/dev/null 2>&1; then
  echo "[auto-pr-responder] INFO: git リポジトリを検出" >&2
fi

exit 0
