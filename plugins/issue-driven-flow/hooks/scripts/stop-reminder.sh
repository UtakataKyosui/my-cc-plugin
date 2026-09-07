#!/usr/bin/env bash
# Stop hook: PR レビュー修正の push・返信忘れ防止リマインダー
# /tmp/review-fix-plan-*.json または /tmp/pr-triage-*.json が存在する場合に警告
# 常に exit 0（絶対にブロックしない）

set -uo pipefail

FIX_PLAN_COUNT=0
TRIAGE_COUNT=0

# shellcheck disable=SC2012
FIX_PLAN_COUNT=$(ls /tmp/review-fix-plan-*.json 2>/dev/null | wc -l | tr -d ' ') || true
# shellcheck disable=SC2012
TRIAGE_COUNT=$(ls /tmp/pr-triage-*.json 2>/dev/null | wc -l | tr -d ' ') || true

if [ "$FIX_PLAN_COUNT" -eq 0 ] && [ "$TRIAGE_COUNT" -eq 0 ]; then
  exit 0
fi

if [ "$FIX_PLAN_COUNT" -gt 0 ]; then
  # shellcheck disable=SC2012
  FIX_PLAN_FILES=$(ls /tmp/review-fix-plan-*.json 2>/dev/null | tr '\n' ' ') || true
  echo "[auto-pr-responder] 未処理のレビュー修正プランが ${FIX_PLAN_COUNT} 件あります。" >&2
  echo "  → push しましたか？（jj safe-push / git push）" >&2
  echo "  → 修正プランファイル: $FIX_PLAN_FILES" >&2
fi

if [ "$TRIAGE_COUNT" -gt 0 ]; then
  # shellcheck disable=SC2012
  TRIAGE_FILES=$(ls /tmp/pr-triage-*.json 2>/dev/null | tr '\n' ' ') || true
  echo "[auto-pr-responder] 未送信の triage 結果が ${TRIAGE_COUNT} 件あります。" >&2
  echo "  → PR の返信投稿が完了しましたか？" >&2
  echo "  → triage ファイル: $TRIAGE_FILES" >&2
fi

exit 0
