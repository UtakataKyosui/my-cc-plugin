#!/usr/bin/env bash
# rewrite-cli.sh のユニットテスト
# 実行: bash hooks/test/rewrite-cli_test.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SCRIPT_DIR/../scripts/rewrite-cli.sh"

PASS=0
FAIL=0

# テストヘルパー
assert_rewrite() {
    local desc="$1"
    local input_cmd="$2"
    local expected_cmd="$3"
    local env_overrides="${4:-}"

    local input
    input=$(jq -n --arg cmd "$input_cmd" '{"tool_input":{"command":$cmd}}')

    local output
    if [[ -n "$env_overrides" ]]; then
        output=$(env "$env_overrides" bash "$HOOK" <<<"$input" 2>/dev/null)
    else
        output=$(bash "$HOOK" <<<"$input" 2>/dev/null)
    fi
    local actual_cmd
    actual_cmd=$(echo "$output" | jq -r '.tool_input.command // empty' 2>/dev/null)

    if [[ "$actual_cmd" == "$expected_cmd" ]]; then
        echo "  PASS: $desc"
        ((PASS++))
    else
        echo "  FAIL: $desc"
        echo "        input:    $input_cmd"
        echo "        expected: $expected_cmd"
        echo "        got:      $actual_cmd"
        ((FAIL++))
    fi
}

assert_passthrough() {
    local desc="$1"
    local input_cmd="$2"
    local env_overrides="${3:-}"

    local input
    input=$(jq -n --arg cmd "$input_cmd" '{"tool_input":{"command":$cmd}}')

    local output
    if [[ -n "$env_overrides" ]]; then
        output=$(env "$env_overrides" bash "$HOOK" <<<"$input" 2>/dev/null)
    else
        output=$(bash "$HOOK" <<<"$input" 2>/dev/null)
    fi

    # 出力が空 → exit 0 で通過したと判断
    if [[ -z "$output" ]]; then
        echo "  PASS: $desc (passthrough)"
        ((PASS++))
    else
        local actual_cmd
        actual_cmd=$(echo "$output" | jq -r '.tool_input.command // empty' 2>/dev/null)
        if [[ "$actual_cmd" == "$input_cmd" ]]; then
            echo "  PASS: $desc (passthrough unchanged)"
            ((PASS++))
        else
            echo "  FAIL: $desc"
            echo "        expected passthrough of: $input_cmd"
            echo "        got:                     $actual_cmd"
            ((FAIL++))
        fi
    fi
}

# jq が必要
if ! command -v jq &>/dev/null; then
    echo "SKIP: jq not found"
    exit 0
fi

echo "=== rewrite-cli.sh tests ==="
echo ""

# ── RUST_CLI_REWRITE=0 で無効化 ──────────────────────────────────────────────
echo "--- 無効化 ---"
# eza がインストールされていても RUST_CLI_REWRITE=0 なら通過
if command -v eza &>/dev/null; then
    assert_passthrough "RUST_CLI_REWRITE=0 でリライト無効" "ls -la" "RUST_CLI_REWRITE=0"
fi

# ── ls → eza ─────────────────────────────────────────────────────────────────
if command -v eza &>/dev/null; then
    echo ""
    echo "--- ls → eza ---"
    assert_rewrite "ls のみ" \
        "ls" \
        "eza --git --icons --group-directories-first"
    assert_rewrite "ls -la" \
        "ls -la" \
        "eza -la --git --icons --group-directories-first"
    assert_rewrite "ls -la path/" \
        "ls -la path/" \
        "eza -la path/ --git --icons --group-directories-first"
    assert_rewrite "rtk ls" \
        "rtk ls" \
        "rtk eza --git --icons --group-directories-first"
    assert_rewrite "rtk ls（複数スペース）" \
        "rtk  ls -la" \
        "rtk eza -la --git --icons --group-directories-first"
fi

# ── cat → bat ────────────────────────────────────────────────────────────────
if command -v bat &>/dev/null; then
    echo ""
    echo "--- cat → bat ---"
    assert_rewrite "cat <file>" \
        "cat README.md" \
        "bat --plain README.md"
    # パイプは通過
    assert_passthrough "cat | grep はスキップ" \
        "cat file.txt | grep pattern"
    # 複数ファイルは通過
    assert_passthrough "cat 複数ファイルはスキップ" \
        "cat file1.txt file2.txt"
fi

# ── grep -r → rg ─────────────────────────────────────────────────────────────
if command -v rg &>/dev/null; then
    echo ""
    echo "--- grep -r → rg ---"
    assert_rewrite "grep -r pattern dir" \
        "grep -r \"pattern\" src/" \
        "rg \"pattern\" src/"
    assert_rewrite "grep -rn pattern dir" \
        "grep -rn \"pattern\" src/" \
        "rg -n \"pattern\" src/"
    assert_rewrite "grep -ri pattern dir" \
        "grep -ri \"pattern\" src/" \
        "rg -i \"pattern\" src/"
    # -r なしは通過
    assert_passthrough "grep -n はスキップ" \
        "grep -n pattern file.txt"
fi

# ── du → dust ────────────────────────────────────────────────────────────────
# dust は du のフラグ非互換のため、フラグなし・パスのみの場合のみリライト
if command -v dust &>/dev/null; then
    echo ""
    echo "--- du → dust ---"
    assert_rewrite "du のみ" \
        "du" \
        "dust"
    assert_rewrite "du ." \
        "du ." \
        "dust ."
    assert_rewrite "du /path" \
        "du /tmp" \
        "dust /tmp"
    assert_passthrough "du -sh . はスキップ（dust はフラグ非互換）" \
        "du -sh ."
    assert_passthrough "du -ah はスキップ" \
        "du -ah"
fi

# ── ps → procs ───────────────────────────────────────────────────────────────
# procs は ps のフラグを解釈しないため、フラグなしの場合のみリライト
if command -v procs &>/dev/null; then
    echo ""
    echo "--- ps → procs ---"
    assert_rewrite "ps のみ" \
        "ps" \
        "procs"
    assert_passthrough "ps aux はスキップ（procs はフラグ非互換）" \
        "ps aux"
fi

# ── diff → delta ─────────────────────────────────────────────────────────────
if command -v delta &>/dev/null; then
    echo ""
    echo "--- diff → delta ---"
    assert_rewrite "diff file1 file2" \
        "diff file1.txt file2.txt" \
        "delta file1.txt file2.txt"
fi

# ── hexdump → hexyl ──────────────────────────────────────────────────────────
if command -v hexyl &>/dev/null; then
    echo ""
    echo "--- hexdump → hexyl ---"
    assert_rewrite "hexdump -C file.bin" \
        "hexdump -C file.bin" \
        "hexyl file.bin"
    assert_rewrite "hexdump file.bin" \
        "hexdump file.bin" \
        "hexyl file.bin"
fi

# ── tree → tre ───────────────────────────────────────────────────────────────
if command -v tre &>/dev/null; then
    echo ""
    echo "--- tree → tre ---"
    assert_rewrite "tree" \
        "tree" \
        "tre"
    assert_rewrite "tree -L 2" \
        "tree -L 2" \
        "tre -L 2"
fi

# ── jq → jaq ─────────────────────────────────────────────────────────────────
if command -v jaq &>/dev/null; then
    echo ""
    echo "--- jq → jaq ---"
    assert_rewrite "jq '.foo'" \
        "jq '.foo' data.json" \
        "jaq '.foo' data.json"
fi

# ── find → fd ─────────────────────────────────────────────────────────────────
if command -v fd &>/dev/null; then
    echo ""
    echo "--- find → fd ---"
    assert_rewrite "find . -name '*.rs'" \
        "find . -name '*.rs'" \
        "fd -e rs"
    assert_rewrite "find . -name \"*.ts\"（ダブルクォート）" \
        'find . -name "*.ts"' \
        "fd -e ts"
    assert_rewrite "find . -name 'foo'（glob なし）" \
        "find . -name 'foo'" \
        "fd -g foo"
    assert_rewrite "find . -type f -name '*.txt'" \
        "find . -type f -name '*.txt'" \
        "fd -t f -e txt"
    assert_rewrite "find . -type d -name 'src'" \
        "find . -type d -name 'src'" \
        "fd -t d -g src"
    assert_rewrite "find /path -name '*.rs'" \
        "find /path -name '*.rs'" \
        "fd -e rs /path"
    assert_rewrite "find . -name '*.rs' -type f（-type が後）" \
        "find . -name '*.rs' -type f" \
        "fd -t f -e rs"
    assert_passthrough "find -exec は通過" \
        "find . -name '*.rs' -exec grep {} \\;"
    assert_passthrough "find -mtime は通過" \
        "find . -mtime -7"
    assert_passthrough "find -maxdepth は通過" \
        "find . -maxdepth 2 -name '*.ts'"
    assert_passthrough "find -not は通過" \
        "find . -not -name '*.rs'"
    assert_passthrough "find -name 'foo*' glob は通過" \
        "find . -name 'foo*'"
    assert_passthrough "find 複数パスは通過" \
        "find dir1 dir2 -name '*.rs'"
fi

# ── sed はリライトしない ──────────────────────────────────────────────────────
# sd はファイルをインプレース編集するため、sed 's/…/g' file（stdout 出力）とは等価でない
echo ""
echo "--- sed はリライトしない ---"
assert_passthrough "sed 's/foo/bar/g' file は通過" \
    "sed 's/foo/bar/g' file.txt"
assert_passthrough "sed -i 's/foo/bar/g' file は通過" \
    "sed -i 's/foo/bar/g' file.txt"
assert_passthrough "RUST_CLI_REWRITE_LIST=sed でも通過" \
    "sed 's/foo/bar/g' file.txt" \
    "RUST_CLI_REWRITE_LIST=sed"

# ── 既存 Rust ツールはスキップ ───────────────────────────────────────────────
echo ""
echo "--- 既存 Rust ツールはスキップ ---"
assert_passthrough "eza はリライトしない" "eza -la"
assert_passthrough "rg はリライトしない" "rg pattern src/"
assert_passthrough "bat はリライトしない" "bat README.md"

# ── RUST_CLI_REWRITE_LIST で対象を絞り込み ──────────────────────────────────
echo ""
echo "--- RUST_CLI_REWRITE_LIST による絞り込み ---"
if command -v eza &>/dev/null && command -v dust &>/dev/null; then
    assert_rewrite "ls のみ対象（du はスキップ）- ls" \
        "ls -la" \
        "eza -la --git --icons --group-directories-first" \
        "RUST_CLI_REWRITE_LIST=ls"
    assert_passthrough "ls のみ対象（du はスキップ）- du" \
        "du -sh ." \
        "RUST_CLI_REWRITE_LIST=ls"
fi

# ── 結果表示 ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="

[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
