#!/usr/bin/env bash
# routing.sh — ロール(role) からモデル・effort・ツール権限・junct フェーズを
# 引き出す唯一の定義元。herdr のペイン経路(flow_agent_start_role)と
# 軽量経路(agents/role-*.md)の両方がここを参照する。
#
# 提供する関数:
#   route_model <role>            モデル名を返す
#   route_effort <role>            effort を返す
#   route_policy <role>            ポリシー名(readonly|write)を返す
#   route_grace_ms <role>          起動後の投入猶予(ms)を返す
#   route_kick_ms <role>           投入完了とみなす待ち時間(ms)を返す
#   route_junct_phase <role>       junct の開始関数名を返す
#   route_args_into <配列名> <role> claude CLI 引数ベクタを呼び出し側の配列へ詰める
#   route_frontmatter_tools <role> 軽量経路の tools: フロントマター値を返す(未定義ならエラー)
#   route_table                    ロール表とポリシー表を人が読める形で出力する
#
# このファイルは source される前提のため、set や shopt で呼び出し側の
# シェルオプションを変更しない。ただし route_die はエラー時に exit 1 する
# (flow_die と同じ約束事)。source する側は set -euo pipefail のスクリプトを
# 前提にし、対話シェルへ直接 source して使うことは想定していない。
#
# データは data/roles.json, data/policies.json, data/agent-tools.json にある。
# 散文のルール(rules/agent-routing.md)にモデル名や effort の値を書かない。
# 値を知りたいときは route_table を実行する。値の重複を避けるためである。

AGENT_ROUTING_DIR="${AGENT_ROUTING_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/data}"
# AGENT_ROUTING_ROLES を指定すると roles.json の場所だけを差し替えられる。
# ~/.claude/hooks/run-design-review.sh や別プラグイン agent-router のように
# このプラグイン外から roles.json だけを参照したい呼び出し元向けの経路。
ROUTE_ROLES_JSON="${AGENT_ROUTING_ROLES:-$AGENT_ROUTING_DIR/roles.json}"
ROUTE_POLICIES_JSON="$AGENT_ROUTING_DIR/policies.json"
ROUTE_AGENT_TOOLS_JSON="$AGENT_ROUTING_DIR/agent-tools.json"

route_die() {
  printf '\033[31merror:\033[0m %s\n' "$*" >&2
  exit 1
}

_route_check_deps() {
  command -v jq >/dev/null || route_die "jq が PATH にない"
  [ -f "$ROUTE_ROLES_JSON" ] || route_die "roles.json が見つからない: $ROUTE_ROLES_JSON"
  [ -f "$ROUTE_POLICIES_JSON" ] || route_die "policies.json が見つからない: $ROUTE_POLICIES_JSON"
}

# 上書き用の環境変数名を作る。role 名は英数字とハイフンのみを前提にする。
_route_env_name() {
  local prefix="$1" role="$2"
  printf '%s_%s' "$prefix" "$(printf '%s' "$role" | tr '[:lower:]-' '[:upper:]_')"
}

_route_field() {
  local role="$1" field="$2" val
  _route_check_deps
  val=$(jq -r --arg r "$role" --arg f "$field" '.[$r][$f] // empty' "$ROUTE_ROLES_JSON")
  [ -n "$val" ] || route_die "role '$role' に $field が定義されていない(roles.json を確認する)"
  printf '%s\n' "$val"
}

route_model() {
  local role="$1" env_name val
  env_name=$(_route_env_name AGENT_ROUTE_MODEL "$role")
  val="${!env_name:-}"
  [ -n "$val" ] && { printf '%s\n' "$val"; return 0; }
  _route_field "$role" model
}

route_effort() {
  local role="$1" env_name val
  env_name=$(_route_env_name AGENT_ROUTE_EFFORT "$role")
  val="${!env_name:-}"
  [ -n "$val" ] && { printf '%s\n' "$val"; return 0; }
  _route_field "$role" effort
}

route_policy() { _route_field "$1" policy; }
route_junct_phase() { _route_field "$1" junct_phase; }
route_grace_ms() { _route_field "$1" grace_ms; }
route_kick_ms() { _route_field "$1" kick_wait_ms; }

# 軽量経路(agents/role-*.md)の tools: 値。未定義のロール(fix/triage/design など
# ペインしか持たないロール)に対しては空を返さずエラーにする。呼び出し側が
# 「軽量経路が存在しないロールを軽量経路で使おうとした」ことに気付けるようにする。
route_frontmatter_tools() {
  local role="$1" val
  command -v jq >/dev/null || route_die "jq が PATH にない"
  [ -f "$ROUTE_AGENT_TOOLS_JSON" ] || route_die "agent-tools.json が見つからない: $ROUTE_AGENT_TOOLS_JSON"
  val=$(jq -r --arg r "$role" '.[$r].tools // empty' "$ROUTE_AGENT_TOOLS_JSON")
  [ -n "$val" ] || route_die "role '$role' に軽量経路(agents/role-*.md)が定義されていない。herdr のペイン経路を使う"
  printf '%s\n' "$val"
}

_route_policy_list_into() {
  local __outname="$1" policy="$2" field="$3"
  local -n __out="$__outname"
  __out=()
  local line
  while IFS= read -r line; do
    [ -n "$line" ] && __out+=("$line")
  done < <(jq -r --arg p "$policy" --arg f "$field" '.[$p][$f][]? // empty' "$ROUTE_POLICIES_JSON")
}

# claude CLI の引数ベクタを組み立てて配列へ詰める。stdout では返さない。
# stdout 経由にすると呼び出し側が read -r -a で受け直すことになり、
# 空白を含む引数(例: 将来 "Bash(git *)" のような形を使う場合)が IFS 分割で
# 壊れる。nameref で直接詰めることでこの経路を作らない。
#
# 使い方: local args=(); route_args_into args review
route_args_into() {
  local __outname="$1" role="$2"
  local -n __out="$__outname"
  _route_check_deps
  local model effort policy
  model=$(route_model "$role")
  effort=$(route_effort "$role")
  policy=$(route_policy "$role")

  local allowed=() disallowed=()
  _route_policy_list_into allowed "$policy" allowed
  _route_policy_list_into disallowed "$policy" disallowed

  __out=(--model "$model" --effort "$effort")
  [ "${#allowed[@]}" -gt 0 ] && __out+=(--allowed-tools "${allowed[@]}")
  [ "${#disallowed[@]}" -gt 0 ] && __out+=(--disallowed-tools "${disallowed[@]}")

  # 末尾への追加のみ許可する。置換はしない。置換方式(旧 RRAR_AGENT_ARGS/
  # PRAR_AGENT_ARGS)はガードレールの disallowed-tools を丸ごと落とせてしまう。
  # AGENT_ROUTE_EXTRA_ARGS に空白を含む引数を渡す必要がある場合は、
  # そのフラグ自体を Bash(git:*) のようなコロン区切りの形で表現する。
  if [ -n "${AGENT_ROUTE_EXTRA_ARGS:-}" ]; then
    local extra=()
    # shellcheck disable=SC2206
    extra=(${AGENT_ROUTE_EXTRA_ARGS})
    __out+=("${extra[@]}")
  fi
}

route_table() {
  _route_check_deps
  printf '## roles\n\n'
  printf '%-10s %-8s %-8s %-10s %-20s %-8s %-8s %-10s\n' \
    role model effort policy junct_phase grace_ms kick_ms status
  jq -r 'to_entries[] | [.key, .value.model, .value.effort, .value.policy, .value.junct_phase, (.value.grace_ms|tostring), (.value.kick_wait_ms|tostring), .value.status] | @tsv' \
    "$ROUTE_ROLES_JSON" | while IFS=$'\t' read -r role model effort policy phase grace kick status; do
    printf '%-10s %-8s %-8s %-10s %-20s %-8s %-8s %-10s\n' "$role" "$model" "$effort" "$policy" "$phase" "$grace" "$kick" "$status"
  done
  printf '\n## policies\n\n'
  jq -r 'keys[]' "$ROUTE_POLICIES_JSON" | while IFS= read -r p; do
    printf '%s:\n' "$p"
    printf '  allowed: %s\n' "$(jq -r --arg p "$p" '.[$p].allowed | join(" ")' "$ROUTE_POLICIES_JSON")"
    printf '  disallowed: %s\n' "$(jq -r --arg p "$p" '.[$p].disallowed | join(" ")' "$ROUTE_POLICIES_JSON")"
  done
  if [ -f "$ROUTE_AGENT_TOOLS_JSON" ]; then
    printf '\n## lightweight path (agents/role-*.md)\n\n'
    jq -r 'to_entries[] | "\(.key): \(.value.agent_file)  tools: \(.value.tools)"' \
      "$ROUTE_AGENT_TOOLS_JSON"
  fi
}
