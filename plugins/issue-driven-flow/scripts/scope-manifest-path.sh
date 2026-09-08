#!/usr/bin/env bash
# scope-manifest-path.sh — print the resolved scope-manifest path for the
# current repo. SINGLE source of truth shared by the manifest WRITER (the
# change-planner agent) and the READER (the `safe-new` jj alias), so the two
# never disagree on where the manifest lives.
#
# IMPORTANT: the path DERIVATION (repo-id hash + XDG location) must stay identical
# to aliases/safe-new/run.sh, or writer and reader disagree. This helper additionally
# falls back to `jj workspace root` when invoked directly (safe-new only ever runs as
# a jj alias, where JJ_WORKSPACE_ROOT is always set). A mismatch silently breaks it.
#
# Resolution order:
#   1. $JJ_SCOPE_FILE if set (explicit override).
#   2. else a per-repo file OUTSIDE the repo (so it is never committed):
#      ${XDG_STATE_HOME:-$HOME/.local/state}/jj-safe-new/<repo-id>.json
#      where <repo-id> = <basename>-<sha1(abs workspace root)[:16]>.
#
# Usage: scripts/scope-manifest-path.sh   # prints the path to stdout
set -uo pipefail

# jj sets JJ_WORKSPACE_ROOT when run as an alias; fall back to `jj workspace
# root` when this script is invoked directly (e.g. by the change-planner agent)
# so it resolves the repo root even from a subdirectory.
#
# Fail closed if neither is available: silently falling back to the current
# directory would derive a <repo-id> from the wrong path, so the WRITER
# (change-planner) and the READER (safe-new) would compute different manifest
# paths and never agree. Point the user at the JJ_SCOPE_FILE escape hatch instead.
workspace_root="${JJ_WORKSPACE_ROOT:-$(jj workspace root 2>/dev/null)}"
if [ -z "$workspace_root" ]; then
	echo "scope-manifest-path: not in a jj workspace (JJ_WORKSPACE_ROOT unset and 'jj workspace root' failed); cannot derive the manifest path. Set JJ_SCOPE_FILE." >&2
	exit 1
fi
cd "$workspace_root" || exit 1

if [ -n "${JJ_SCOPE_FILE:-}" ]; then
	printf '%s\n' "$JJ_SCOPE_FILE"
	exit 0
fi

repo_root=$(pwd -P)
if command -v shasum >/dev/null 2>&1; then
	repo_hash=$(printf '%s' "$repo_root" | shasum | cut -d' ' -f1)
elif command -v sha1sum >/dev/null 2>&1; then
	repo_hash=$(printf '%s' "$repo_root" | sha1sum | cut -d' ' -f1)
else
	repo_hash=$(printf '%s' "$repo_root" | cksum | tr -d ' \t')
fi
repo_id="$(basename "$repo_root")-${repo_hash:0:16}"

# Guard HOME: under `set -u`, ${XDG_STATE_HOME:-$HOME/...} aborts with an
# unbound-variable error if HOME is also unset (e.g. minimal CI). Fail closed
# with a clear message pointing at the JJ_SCOPE_FILE escape hatch instead.
state_base="${XDG_STATE_HOME:-}"
if [ -z "$state_base" ]; then
	if [ -z "${HOME:-}" ]; then
		echo "scope-manifest-path: neither XDG_STATE_HOME nor HOME is set; cannot locate the scope manifest. Set JJ_SCOPE_FILE." >&2
		exit 1
	fi
	state_base="$HOME/.local/state"
fi
printf '%s\n' "$state_base/jj-safe-new/${repo_id}.json"
