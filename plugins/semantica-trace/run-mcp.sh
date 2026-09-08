#!/bin/sh
# semantica-trace の照会専用 MCP サーバーを隔離 venv で起動する。
# venv の作り方は skills/semantica-trace/SKILL.md の「前提」節にある。
set -eu

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")" && pwd)}"
VENV_PY="${SEMANTICA_TRACE_PYTHON:-$HOME/.cache/semantica-trace/.venv/bin/python}"

if [ ! -x "$VENV_PY" ]; then
    echo "semantica-trace: 隔離 venv が見つかりません: $VENV_PY" >&2
    echo "SKILL.md の「前提」節に従って venv を作成してください。" >&2
    exit 1
fi

exec "$VENV_PY" "$PLUGIN_ROOT/skills/semantica-trace/mcp_server.py"
