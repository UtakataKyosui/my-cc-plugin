#!/usr/bin/env bash
# PreToolUse hook (Bash matcher): block direct `jj new` / `jj git push` and
# redirect to the guarded `jj safe-new` / `jj safe-push` aliases.
#
# Pass-through: `jj safe-new` / `jj safe-push` (the aliases themselves) and
# `command jj new` / `command jj git push` (intentional in-script bypass).
# Both allowed forms are neutralized to placeholders BEFORE matching, so a
# direct execution combined with an allowed one (e.g.
# `jj git push && command jj git push`) is still blocked on the direct part.
#
# Fail-OPEN: if jq is unavailable, or fails to parse stdin (unexpected/non-JSON
# payload), we exit 0 (do not block). A safety guard must never wedge the user's
# shell because a dependency is missing or the input is odd — the worst case is
# one direct command slipping through, not a broken session.
#
# Distributed with issue-driven-flow; the safe-* aliases
# this hook points at are installed separately by `just sync` (see the repo
# README). Without those aliases the redirect targets won't exist, so install
# both for a complete standalone safety net.
set -euo pipefail

if ! command -v jq > /dev/null 2>&1; then
    exit 0
fi

INPUT=$(cat)
# `|| true`: under `set -euo pipefail` a jq parse failure would otherwise abort
# the hook (non-zero exit) instead of failing open. Degrade to an empty command
# so the `[ -z ]` guard below exits 0.
COMMAND=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)

[ -z "$COMMAND" ] && exit 0

# Trailing boundary after the subcommand: end-of-line, or any char that can't be
# part of an identifier. This blocks `jj new;` / `jj new&&…` / `$(jj new)` while
# NOT matching unrelated words like `jj newfoo` or `jj git pushme`.
BOUNDARY='($|[^[:alnum:]_-])'

# ─── Block direct `jj new` ─────────────────────────────────────────────────
# Neutralize the allowed forms first so the generic `jj new` matcher can't catch
# them: `jj safe-new` and `command jj new` (script-internal calls).
FILTERED_NEW=$(printf '%s\n' "$COMMAND" | \
    sed -E 's/jj[[:space:]]+safe-new/JJ_SAFE_NEW/g' | \
    sed -E 's/command[[:space:]]+jj[[:space:]]+new/COMMAND_JJ_NEW/g')

if printf '%s\n' "$FILTERED_NEW" | grep -qE "(^|[|&;({[:space:]])jj[[:space:]]+new$BOUNDARY"; then
    echo "jj new の直接実行は禁止されています。jj safe-new を使ってください（スコープチェックと品質確認が実行されます）。" >&2
    echo "例: jj safe-new -m \"feat: 次のChange名\"" >&2
    exit 2
fi

# ─── Block direct `jj git push` ────────────────────────────────────────────
# Neutralize the allowed `command jj git push` bypass to a placeholder first
# (same approach as `jj new`), so a direct push combined with a bypass — e.g.
# `jj git push && command jj git push` — is still blocked on the direct part.
FILTERED_PUSH=$(printf '%s\n' "$COMMAND" | \
    sed -E 's/command[[:space:]]+jj[[:space:]]+git[[:space:]]+push/COMMAND_JJ_GIT_PUSH/g')

if printf '%s\n' "$FILTERED_PUSH" | grep -qE "(^|[|&;({[:space:]])jj[[:space:]]+git[[:space:]]+push$BOUNDARY"; then
    echo "jj git push の直接実行は禁止されています。jj safe-push を使ってください（diverge/conflict チェックと品質確認が実行されます）。" >&2
    exit 2
fi

exit 0
