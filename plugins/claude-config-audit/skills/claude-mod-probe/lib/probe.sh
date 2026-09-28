#!/usr/bin/env bash
# Claude Code の engine 内部を、使い捨ての function hooks プラグインで観測する。
#
# 前提: claude CLI が PATH にあること。観測結果は $.fs.write でファイルへ出す。
# $.ui.log は -p の stream-json に出ないため使わない（実測で確認済み）。
#
# rm は command 経由で呼ぶ。利用者のシェルが rm を rip などへ別名定義している
# 場合、-f が未知の引数として弾かれる。

set -euo pipefail

PROBE_ROOT="${PROBE_ROOT:-${TMPDIR:-/tmp}/claude-mod-probe}"

# probe_init <name>
# 使い捨てプラグインの骨組みを作り、そのディレクトリを stdout に返す。
probe_init() {
  local name="$1" dir="$PROBE_ROOT/$1"
  mkdir -p "$dir/.claude-plugin" "$dir/hooks"
  cat > "$dir/.claude-plugin/plugin.json" <<JSON
{ "name": "$name", "version": "0.0.1", "description": "engine を観測する使い捨てプラグイン" }
JSON
  printf '{ "modules": ["./register.ts"] }\n' > "$dir/hooks/hooks.json"
  printf '%s\n' "$dir"
}

# probe_module <dir> <module-path> <out-path>
# 観測モジュールを置く。モジュール内の __OUT__ を出力先へ差し替える。
probe_module() {
  local dir="$1" module="$2" out="$3"
  sed "s|__OUT__|$out|g" "$module" > "$dir/hooks/register.ts"
  ( cd "$dir" && claude plugin validate . >/dev/null )
}

# probe_run <dir> <out-path> [prompt]
# 短いセッションを1回走らせる。プロンプト提出とプロンプト組み立てまでを観測する。
probe_run() {
  local dir="$1" out="$2" prompt="${3:-ok}"
  command rm -f "$out"
  claude -p "$prompt" --plugin-dir "$dir" >/dev/null 2>&1 || true
  cat "$out" 2>/dev/null || printf '(出力なし)\n'
}

# probe_run_while <dir> <out-path> <seconds> <command...>
# セッションを走らせたまま command を実行する。ファイル監視や、セッション途中
# でしか起きない事象の観測に使う。claude 側は Bash で sleep して時間を稼ぐ。
probe_run_while() {
  local dir="$1" out="$2" seconds="$3"; shift 3
  command rm -f "$out"
  claude -p "Bash ツールで 'sleep $seconds && echo done' を実行して、その後 ok と答えて" \
    --plugin-dir "$dir" --allowedTools Bash >/dev/null 2>&1 &
  local pid=$!
  python3 -c "import time; time.sleep($seconds / 2)"
  "$@"
  wait "$pid" || true
  cat "$out" 2>/dev/null || printf '(出力なし)\n'
}

# probe_clean
probe_clean() { command rm -rf "$PROBE_ROOT"; }
