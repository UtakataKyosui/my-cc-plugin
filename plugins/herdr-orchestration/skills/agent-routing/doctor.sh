#!/usr/bin/env bash
# doctor.sh — agent-routing の定義が整合しているかを自己診断する。
#
# 使い方:
#   doctor.sh
#
# 検査する内容:
#   1. roles.json / policies.json / agent-tools.json が妥当な JSON か
#   2. roles.json が参照する policy が policies.json に存在するか
#   3. agent-tools.json が指す agents/role-*.md が実在し、
#      その tools: フロントマターが agent-tools.json の値と一致するか
#   4. route_args_into が空白を含む引数でも壊れずに配列へ詰められるか

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)/agents"
# shellcheck source=lib/routing.sh
source "${AGENT_ROUTING_LIB:-$SCRIPT_DIR/lib/routing.sh}"

PASS=0
FAIL=0
check() {
  local label="$1" ok="$2" detail="${3:-}"
  if [ "$ok" = "1" ]; then
    printf '  \033[32mOK\033[0m   %s %s\n' "$label" "$detail" >&2
    PASS=$((PASS + 1))
  else
    printf '  \033[31mNG\033[0m   %s %s\n' "$label" "$detail" >&2
    FAIL=$((FAIL + 1))
  fi
}

phase() { printf '\n\033[1;36m== %s\033[0m\n' "$*" >&2; }

phase "JSON の妥当性"
for f in "$ROUTE_ROLES_JSON" "$ROUTE_POLICIES_JSON" "$ROUTE_AGENT_TOOLS_JSON"; do
  if jq -e . "$f" >/dev/null 2>&1; then
    check "$(basename "$f") は妥当な JSON" 1
  else
    check "$(basename "$f") は妥当な JSON" 0 "$f"
  fi
done

phase "roles.json が参照する policy の実在"
while IFS=$'\t' read -r role policy; do
  if jq -e --arg p "$policy" 'has($p)' "$ROUTE_POLICIES_JSON" >/dev/null 2>&1; then
    check "role '$role' の policy '$policy'" 1
  else
    check "role '$role' の policy '$policy'" 0 "policies.json に存在しない"
  fi
done < <(jq -r 'to_entries[] | [.key, .value.policy] | @tsv' "$ROUTE_ROLES_JSON")

phase "軽量経路(agents/role-*.md)とのフロントマター一致"
while IFS=$'\t' read -r role file tools; do
  path="$AGENTS_DIR/$file"
  if [ ! -f "$path" ]; then
    check "role '$role' の $file" 0 "ファイルが存在しない: $path"
    continue
  fi
  # フロントマターの tools: 行を取り出す(YAML の1行想定)
  actual=$(awk -F': ' '/^tools:/{print $2; exit}' "$path")
  if [ "$actual" = "$tools" ]; then
    check "role '$role' の tools: フロントマター" 1 "($tools)"
  else
    check "role '$role' の tools: フロントマター" 0 "期待='$tools' 実際='$actual'"
  fi
  model_line=$(awk -F': ' '/^model:/{print $2; exit}' "$path")
  expected_model=$(route_model "$role" 2>/dev/null || echo "")
  if [ "$model_line" = "$expected_model" ]; then
    check "role '$role' の model: フロントマター" 1 "($model_line)"
  else
    check "role '$role' の model: フロントマター" 0 "期待='$expected_model' 実際='$model_line'"
  fi
  effort_line=$(awk -F': ' '/^effort:/{print $2; exit}' "$path")
  expected_effort=$(route_effort "$role" 2>/dev/null || echo "")
  if [ "$effort_line" = "$expected_effort" ]; then
    check "role '$role' の effort: フロントマター" 1 "($effort_line)"
  else
    check "role '$role' の effort: フロントマター" 0 "期待='$expected_effort' 実際='$effort_line'"
  fi
done < <(jq -r 'to_entries[] | [.key, .value.agent_file, .value.tools] | @tsv' "$ROUTE_AGENT_TOOLS_JSON")

phase "route_args_into が空白を含む引数を壊さないか"
AGENT_ROUTE_EXTRA_ARGS="" # 明示的に空にして既定の振る舞いを見る
args=()
route_args_into args review
# --allowed-tools の直後の要素群に "Bash(gh:*)" が1要素のまま入っているかを確認する
found=0
for a in "${args[@]}"; do
  [ "$a" = "Bash(gh:*)" ] && found=1
done
check "Bash(gh:*) が1要素のまま渡る" "$found" "argc=${#args[@]}"

phase "結果"
printf '  合格 %s / 不合格 %s\n' "$PASS" "$FAIL" >&2
[ "$FAIL" -eq 0 ]
