#!/usr/bin/env bash
# SessionStart 統合オーケストレーター
# 各プラグインの SessionStart スクリプトを冪等に実行する
# 子スクリプトは hookSpecificOutput JSON を stdout に出力するためパススルーする
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

run_section() {
  local script="$1"
  if [[ -f "$script" ]]; then
    bash "$script" || true
  fi
}

# 1. ツール存在チェック（harness-toolkit 由来）
run_section "$SCRIPT_DIR/check-tools.sh"

# 2. jj / VCS 状態ロード（vcs-workflow 由来）
run_section "$SCRIPT_DIR/load-session.sh"

# 3. PR / Issue タスク通知（gh-my-task 由来）
run_section "$SCRIPT_DIR/session-task-notify.sh"

# 4. Stale ブランチ通知（branch-cleanup 由来）
run_section "$SCRIPT_DIR/session-stale-notify.sh"

# 5. PR ワークフロー事前チェック（pr-workflow 由来）
run_section "$SCRIPT_DIR/session-precheck.sh"

exit 0
