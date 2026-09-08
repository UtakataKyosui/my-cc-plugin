#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
HOOK="$ROOT/plugins/issue-driven-flow/hooks/scripts/jj-block-direct.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cat >"$TMP/jj" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == "config get aliases.safe-new" || "$*" == "config get aliases.safe-push" ]]; then
  exit "${JJ_TEST_ALIAS_STATUS:-1}"
fi
exit 0
EOF
chmod +x "$TMP/jj"

payload='{"tool_input":{"command":"jj git push --bookmark feat/test"}}'

# With no safe-* aliases, the documented plain-jj fallback must remain allowed.
PATH="$TMP:$PATH" JJ_TEST_ALIAS_STATUS=1 "$HOOK" <<<"$payload"

# When safe-* aliases are installed, direct push must be blocked.
if PATH="$TMP:$PATH" JJ_TEST_ALIAS_STATUS=0 "$HOOK" <<<"$payload"; then
  echo "expected direct jj git push to be blocked when safe-push is configured" >&2
  exit 1
fi

echo "jj-block-direct fallback/guard checks passed"
