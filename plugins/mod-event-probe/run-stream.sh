#!/usr/bin/env bash
# 使い方: run-stream.sh "<プロンプト>" [claude への追加引数 ...]
# vibe-kanban 系の executor と同じ stream-json 入出力で起動し、フックの記録と sink への POST を表示する
set -euo pipefail
SKILL_DIR="${MOD_EVENT_PROBE_HOME:-${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")" && pwd)}}"
LOG=/tmp/mod-event-probe.jsonl
SINK_OUT=/tmp/mod-event-probe-sink.jsonl
PORT="${MOD_PROBE_PORT:-18765}"
prompt="$1"; shift
rm -f "$LOG" "$SINK_OUT"

python3 "$SKILL_DIR/sink.py" "$PORT" "$SINK_OUT" &
sink_pid=$!
trap 'kill "$sink_pid" 2>/dev/null || true' EXIT

msg=$(python3 -c 'import json,sys; print(json.dumps({"type":"user","message":{"role":"user","content":sys.argv[1]}}))' "$prompt")
(cd /tmp && printf '%s\n' "$msg" | CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 \
  MOD_PROBE_SINK="http://127.0.0.1:$PORT/" MOD_PROBE_TASK_ID="probe-task-1" \
  claude -p --setting-sources project --plugin-dir "$SKILL_DIR" \
  --verbose --output-format=stream-json --input-format=stream-json \
  --include-partial-messages --replay-user-messages \
  --permission-mode bypassPermissions "$@" > /tmp/mod-event-probe-stdout.jsonl 2>/tmp/mod-event-probe-stderr.log) || true

echo "## hook log ($LOG)"; cat "$LOG" 2>/dev/null || echo "(none)"
echo "## sink ($SINK_OUT)"; cat "$SINK_OUT" 2>/dev/null || echo "(none)"
