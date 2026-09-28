#!/usr/bin/env bash
set -euo pipefail

# setup-worktree-auto.sh （個人グローバル版 / ~/.claude/hooks）
# worktree 作成を検出し、環境整備スクリプト（~/.claude/scripts/setup-worktree.sh）を自動実行する。
#
# トリガー（~/.claude/settings.json の PostToolUse に登録）:
#   - matcher "Bash"          : `git worktree add` コマンド実行時
#   - matcher "EnterWorktree" : EnterWorktree ツール実行時
#
# 設計方針:
#   - worktree パスは「明示的な情報源」からのみ取得する（Bash はコマンド引数、EnterWorktree は入力フィールド）。
#   - `git worktree list | tail` のような推定フォールバックはしない。
#     推定は並行実行時に無関係な既存 worktree を誤って対象にしてセットアップを走らせる危険があるため
#     （pppp606 の [imo] 指摘 / 実際に誤適用を確認済み）。
#   - パスを特定できない場合は何もせず終了する。
#   - 共有リポジトリではなく個人設定に置くため、個人環境固有のツール前提を許容する。
#   - 現状の Claude Code 仕様（イベント名・入力スキーマ）に追従して要再検討。

INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null || true)

# メインリポジトリ（worktree list の先頭エントリ）
# git リポジトリ外では git が失敗し grep も 1 を返す。set -e + pipefail でここで落ちて
# 「PostToolUse:Bash hook error（stderr なし）」になるので、空文字にして続ける
MAIN_REPO="$(git worktree list --porcelain 2>/dev/null | grep '^worktree ' | head -1 | sed 's/^worktree //' || true)"
WORKTREE_PATH=""

if [ "$TOOL_NAME" = "Bash" ]; then
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
  # git worktree add 以外はスキップ（remove / list / prune などは対象外）
  if ! echo "$COMMAND" | grep -qE '^[[:space:]]*git[[:space:]]+worktree[[:space:]]+add($|[[:space:]])'; then
    exit 0
  fi
  # `git worktree add <path> [branch]` の <path>（add 以降の最初の非オプション引数）を抽出する。
  WORKTREE_PATH=$(echo "$COMMAND" | awk '{
    seen = 0
    for (i = 1; i <= NF; i++) {
      t = $i
      if (t == "add") { seen = 1; continue }
      if (seen) {
        if (substr(t, 1, 1) == "-") {
          if (t == "-b" || t == "-B" || t == "--reason") { i++ }  # 値を取るフラグはその値もスキップ
          continue
        }
        print t; exit
      }
    }
  }')
else
  # EnterWorktree など: フック入力から worktree パスを取得（スキーマ差異に備え複数候補を許容）
  WORKTREE_PATH=$(echo "$INPUT" | jq -r '.tool_response.path // .tool_response.worktree_path // .tool_input.path // .worktree_path // .path // empty' 2>/dev/null || true)
fi

# パスを特定できなければ、誤った worktree への適用を避けるため推定せず終了する
if [ -z "$WORKTREE_PATH" ]; then
  echo "警告: worktree パスを特定できなかったため自動セットアップをスキップしました (tool_name=${TOOL_NAME:-?})" >&2
  exit 0
fi

# 相対パス（cwd 相対の git worktree add）を絶対パスへ正規化
[ -d "$WORKTREE_PATH" ] || exit 0
WORKTREE_PATH=$(cd "$WORKTREE_PATH" && pwd)

# メインリポジトリ自体はスキップ
[ "$WORKTREE_PATH" = "$MAIN_REPO" ] && exit 0

# 冪等化: セットアップ完了マーカーが存在すればスキップ
if [ -f "$WORKTREE_PATH/.worktree-setup-done" ]; then
  echo "Worktree はすでにセットアップ済みです: $WORKTREE_PATH" >&2
  exit 0
fi

echo "=== Worktree 自動環境整備を開始: $WORKTREE_PATH ===" >&2
cd "$WORKTREE_PATH"
bash "${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}/scripts/setup-worktree.sh" "$MAIN_REPO"
