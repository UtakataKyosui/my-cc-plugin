#!/usr/bin/env bash
# 使い方: run.sh "<プロンプト>" [追加の --plugin-dir ...]
# プローブを読み込んでヘッドレスで実行し、記録したイベントを表示する
set -euo pipefail
PROBE_DIR="${MOD_EVENT_PROBE_DIR:-${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")" && pwd)}}"
LOG=/tmp/mod-event-probe.jsonl
prompt="$1"; shift
rm -f "$LOG"
(cd /tmp && CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude -p --setting-sources project \
  --plugin-dir "$PROBE_DIR" "$@" --permission-mode bypassPermissions "$prompt" < /dev/null >/dev/null 2>&1) || true
cat "$LOG" 2>/dev/null || echo "no events recorded: $LOG" >&2
