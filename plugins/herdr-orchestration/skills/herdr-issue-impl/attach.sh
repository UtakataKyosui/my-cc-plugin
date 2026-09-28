#!/usr/bin/env bash
# run.sh の見張りが先に抜けてしまったエージェントに付き直し、result.json が出るまで待つ。
#
#   attach.sh <agent_name> <issue> <run_dir>
set -uo pipefail
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
source "${HERDR_FLOW_LIB:-$PLUGIN_ROOT/skills/herdr-fanout/lib/flow.sh}"

name="$1"; issue="$2"; run_dir="$3"
dir="$run_dir/$issue"; status="$run_dir/status.log"
st() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" >>"$status"; }

for _ in 1 2 3 4; do
  [ -s "$dir/result.json" ] && break
  waited=0
  while [ "$waited" -lt "${ISSUE_IMPL_RESUME_WAIT_S:-900}" ] && [ ! -s "$dir/result.json" ] \
        && [ "$(flow_agent_status "$name")" = "done" ]; do
    sleep 15; waited=$((waited + 15))
  done
  [ -s "$dir/result.json" ] && break
  if [ "$(flow_agent_status "$name")" = "done" ]; then
    printf '作業を続けてください。完了したら指示どおり %s/result.json を書いてください。\n' "$dir" >"$dir/nudge.txt"
    flow_agent_kick "$name" "$dir/nudge.txt" || true
  fi
  herdr agent wait "$name" --until done --until blocked --timeout 10800000 >/dev/null 2>&1 || true
  if [ "$(flow_agent_status "$name")" = "blocked" ]; then
    st "#$issue BLOCKED ($name)"
    while [ "$(flow_agent_status "$name")" = "blocked" ]; do sleep 15; done
  fi
done

if [ -s "$dir/result.json" ]; then
  st "#$issue DONE $(jq -r '.pr_url // "no-pr"' "$dir/result.json")"
else
  st "#$issue 終了したが result.json が無い (attach)"
fi
