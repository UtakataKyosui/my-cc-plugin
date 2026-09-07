#!/bin/bash
# PostToolUseFailure hook (Bash matcher): harness-toolkit 依存ツールの実行失敗時に診断情報を出力する
# 対象ツール: fd, rg, repomix, semgrep
# (jj 関連の診断は vcs-workflow プラグインに移管)
# 無関係なコマンドは早期リターン。常に exit 0（絶対にブロックしない）。
set -uo pipefail

# jq が利用可能か確認
if ! command -v jq &>/dev/null; then
  exit 0
fi

# stdin から入力を保存（複数回参照できるよう変数に格納）
INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")
if [ -z "$COMMAND" ]; then
  exit 0
fi

# harness-toolkit の対象ツールか判定
is_harness_command() {
  echo "$COMMAND" | grep -qE '\b(fd|rg|repomix|semgrep)\b'
}

if ! is_harness_command; then
  exit 0
fi

# ツール別の診断メッセージを出力
if echo "$COMMAND" | grep -qE '\bsemgrep\b'; then
  echo "harness-toolkit [diagnostic]: semgrep 実行に失敗しました。" >&2
  echo "  確認事項:" >&2
  echo "    - semgrep がインストールされているか: which semgrep" >&2
  echo "    - 設定ファイルが正しいか: semgrep --version" >&2
  echo "    - ネットワーク接続（--config auto はルールを取得します）" >&2
elif echo "$COMMAND" | grep -qE '\brepomix\b'; then
  echo "harness-toolkit [diagnostic]: repomix 実行に失敗しました。" >&2
  echo "  確認事項:" >&2
  echo "    - repomix がインストールされているか: which repomix" >&2
  echo "    - ファイル数が多すぎないか（repomix には上限があります）" >&2
  echo "    - 出力先ディレクトリへの書き込み権限があるか" >&2
elif echo "$COMMAND" | grep -qE '\b(fd|rg)\b'; then
  TOOL=$(echo "$COMMAND" | grep -oE '\b(fd|rg)\b' | head -1)
  echo "harness-toolkit [diagnostic]: $TOOL コマンドが失敗しました。" >&2
  echo "  確認事項:" >&2
  echo "    - $TOOL がインストールされているか: which $TOOL" >&2
  echo "    - 検索対象ディレクトリへのアクセス権限があるか" >&2
fi

exit 0
