#!/usr/bin/env bash
# CwdChanged hook: on directory change, detect a jj repository and surface its
# current state. Non-jj directories return early. NEVER blocks (always exit 0).
set -uo pipefail

# Skip when jj is unavailable.
if ! command -v jj &>/dev/null; then
  exit 0
fi

# Skip outside a jj repository.
if ! jj root &>/dev/null 2>&1; then
  exit 0
fi

# Show the current change and any bookmarks pointing at @.
CHANGE=$(jj log --no-graph --limit 1 --template 'change_id.short(8) ++ " " ++ description.first_line()' 2>/dev/null || echo "")
BOOKMARK=$(jj bookmark list --all 2>/dev/null | grep "@" | head -3 || echo "")

echo "[vcs-workflow] jj リポジトリを検出しました。" >&2
if [ -n "$CHANGE" ]; then
  echo "  現在の change: $CHANGE" >&2
fi
if [ -n "$BOOKMARK" ]; then
  echo "  ブックマーク: $(printf '%s' "$BOOKMARK" | tr '\n' ' ')" >&2
fi

exit 0
