#!/bin/bash
# PostCompact hook: コンテキスト圧縮後に CONTEXT_FULL.md の存在を通知する
# PreCompact (repomix-full.sh) と対称ペアを形成する
set -uo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
OUTPUT_FILE="$PROJECT_DIR/CONTEXT_FULL.md"

if [ -f "$OUTPUT_FILE" ]; then
  FILE_SIZE_KB=$(( $(wc -c < "$OUTPUT_FILE") / 1024 ))
  echo "harness-toolkit [context]: コンテキスト圧縮完了。圧縮前のスナップショットが保存されています。" >&2
  echo "  ファイル: CONTEXT_FULL.md (${FILE_SIZE_KB}KB)" >&2
  echo "  圧縮前の全コンテキストを参照するには: Read CONTEXT_FULL.md" >&2
fi

exit 0
