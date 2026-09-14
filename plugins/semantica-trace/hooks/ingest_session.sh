#!/bin/bash
# SessionEnd hook: 完了したセッションの transcript を semantica の decision graph へ ingest する。
# sui-memory/hooks/session-end-ingest.sh を雛形にしている。重い処理は lib/ingest_cli.py 側にあり、
# このスクリプトは stdin の JSON からパスを解決して呼ぶだけに留める(過去セッションへ
# 遡って再実行するのは ingest_cli.py を直接呼ぶため。rules/script-reuse.md)。
#
# セッション終了をブロックしないよう background で実行し、失敗は握り潰す。

set -euo pipefail

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
# SessionEnd の stdin は transcript_path を直接くれる(実測)。cwd からスラッグを
# 組み立てる方式は、cwd に記号が混ざる場合や将来スラッグ規則が変わった場合に
# 静かに外れるため、来ていればそのまま使う。
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')

if [ -z "$SESSION_ID" ]; then
    exit 0
fi

if [ -z "$TRANSCRIPT_PATH" ]; then
    if [ -z "$CWD" ]; then
        exit 0
    fi
    # Claude Code replaces every non-alnum char (not just "/") with "-" when it
    # derives the project slug — e.g. $HOME/.claude ->
    # -Users-<user>--claude (verified against ~/.claude/projects/*). The
    # sui-memory template this was based on only replaces "/", which silently
    # breaks path resolution whenever $HOME contains a "." (true on this
    # machine for every real session, not just this repo).
    PROJECT_DIR=$(echo "$CWD" | sed 's/[^A-Za-z0-9]/-/g' | sed 's|^-||')
    TRANSCRIPT_PATH="$HOME/.claude/projects/-${PROJECT_DIR}/${SESSION_ID}.jsonl"
fi

# 極端に短いセッションは decision ノードが立たないので捨てる
if [ ! -f "$TRANSCRIPT_PATH" ]; then
    exit 0
fi
FILE_SIZE=$(stat -f%z "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
if [ "$FILE_SIZE" -lt 1024 ]; then
    exit 0
fi

# 隔離 venv。semantica[all] は pinecone-client 依存が壊れており、この venv では
# pinecone へ差し替えてある(NOTES.md §0)。venv が無い環境では黙って何もしない。
# run-mcp.sh と同じく SEMANTICA_TRACE_PYTHON で venv の場所を上書きできる。
VENV_PY="${SEMANTICA_TRACE_PYTHON:-$HOME/.cache/semantica-trace/.venv/bin/python}"
if [ ! -x "$VENV_PY" ]; then
    exit 0
fi

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
SKILL_DIR="$PLUGIN_ROOT/skills/semantica-trace"
DATA_DIR="$HOME/.cache/semantica-trace/data"
mkdir -p "$DATA_DIR"
# transcript にはトークン・env ダンプ・ファイル内容が入る。グラフにも複製されるため
# データディレクトリは本人のみに絞る。
chmod 700 "$DATA_DIR" 2>/dev/null || true

LOG="$HOME/.cache/semantica-trace/ingest.log"
# 失敗時のスタックトレースに transcript の内容が載り得るのでログも本人のみに絞る
touch "$LOG" 2>/dev/null || true
chmod 600 "$LOG" 2>/dev/null || true

cd "$SKILL_DIR"
nohup "$VENV_PY" -m lib.ingest_cli \
    --session-id "$SESSION_ID" \
    --transcript "$TRANSCRIPT_PATH" \
    --project "$CWD" \
    --graph-dir "$DATA_DIR" \
    >> "$LOG" 2>&1 &

exit 0
