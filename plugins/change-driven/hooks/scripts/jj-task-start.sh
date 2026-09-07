#!/usr/bin/env bash
# PostToolUse hook (TaskUpdate matcher): when a task transitions to
# `in_progress`, start the matching jj change via the guarded `jj safe-new`.
#
# Best-effort convenience, NOT a load-bearing part of the safety net — the
# block hook (PreToolUse) and the shell wrapper are what actually enforce
# "use safe-*". This hook only auto-creates the next change when a task starts;
# it never blocks (always exit 0) and degrades gracefully when jj / the alias /
# a scope manifest is missing.
#
# Note: this repo's `jj safe-new` requires a scope manifest by default
# (fail-closed). Without one, safe-new exits non-zero and this hook just prints
# a hint — describe the change / create the manifest first (see change-planner).
set -uo pipefail

INPUT=$(cat)

# Skip safely (never fail the hook) when jq is unavailable.
if ! command -v jq > /dev/null 2>&1; then
    exit 0
fi

TOOL=$(printf '%s\n' "$INPUT" | jq -r '.tool_name // empty' 2>/dev/null)
STATUS=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.status // empty' 2>/dev/null)
TITLE=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.title // empty' 2>/dev/null)

# Fire only when a TaskUpdate flips a task to in_progress with a non-empty title.
[ "$TOOL" = "TaskUpdate" ] || exit 0
[ "$STATUS" = "in_progress" ] || exit 0
[ -n "$TITLE" ] || exit 0

# Skip if jj is not installed.
if ! command -v jj > /dev/null 2>&1; then
    echo "━━━ Change遷移をスキップ: jj コマンドが見つかりません ━━━"
    exit 0
fi

# Skip outside a jj repository.
if ! jj root > /dev/null 2>&1; then
    echo "━━━ Change遷移をスキップ: jj リポジトリではありません ━━━"
    exit 0
fi

# Skip when the current change already carries this title.
CURRENT_DESC=$(jj log -r @ --no-graph -T 'description.first_line()' 2>/dev/null)
if [ "$CURRENT_DESC" = "$TITLE" ]; then
    echo "━━━ Change既存: $TITLE ━━━"
    exit 0
fi

echo "━━━ Change遷移: jj safe-new -m \"$TITLE\" ━━━"
# `command` bypasses the safe-push-shell function wrapper if it is installed.
if ! command jj safe-new -m "$TITLE"; then
    echo "⚠ safe-new の実行に失敗しました（alias 未設定・スコープマニフェスト未作成・jj fix エラーのいずれか）。スコープを用意するか、手動で jj safe-new を実行してください。" >&2
fi

exit 0
