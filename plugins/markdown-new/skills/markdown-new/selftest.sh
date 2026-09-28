#!/usr/bin/env bash
# selftest.sh — lib/markdown-new.sh の判定と、markdown.new・対象サイトの実際の応答を確かめる。
# markdown.new の仕様が変わっていないかを見るために、ネットワーク越しの確認も含める。
# markdown.new へは 1 回の実行で 3 回送る。MDNEW_SELFTEST_OFFLINE=1 でネットワーク越しの確認を飛ばす。

set -uo pipefail
# shellcheck source=SCRIPTDIR/lib/markdown-new.sh
source "${MDNEW_LIB:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/markdown-new.sh}"

pass=0
fail=0
check() {
  local label="$1"
  shift
  if "$@"; then
    echo "PASS $label"
    pass=$((pass + 1))
  else
    echo "FAIL $label"
    fail=$((fail + 1))
  fi
}
allowed() {
  mdnew_relay_allowed "$1" >/dev/null
}
refused() {
  ! mdnew_relay_allowed "$1" >/dev/null
}
refused_with_no_relay() {
  local MDNEW_NO_RELAY=1
  refused "$1"
}
default_path_matches() {
  local MDNEW_OUT_DIR=/x/
  # shellcheck disable=SC2053
  [[ "$(mdnew_default_path "$1")" == $2 ]]
}
rc_of() {
  "$@" >/dev/null 2>&1
  echo $?
}

check "localhost には送らない" refused "http://localhost:3000/"
check "ドットの無いホストには送らない" refused "http://intranet/wiki"
check "プライベートの IPv4 には送らない" refused "http://192.168.1.2/"
check "172.16.0.0/12 には送らない" refused "http://172.20.0.1/"
check "172.32 は送ってよい" allowed "https://172.32.0.1/"
check "IPv6 のリテラルには送らない" refused "http://[::1]:8080/"
check "ユーザー情報の入った URL は送らない" refused "https://user:pass@example.com/"
check "access_token のある URL は送らない" refused "https://example.com/p?a=1&access_token=x"
check "X-Amz-Signature のある URL は送らない" refused "https://example.com/f?X-Amz-Signature=x"
check "key のある URL は送らない" refused "https://example.com/?key=abc"
check "keyword や monkey は認証情報とみなさない" allowed "https://example.com/?keyword=a&q=monkey"
check "MDNEW_NO_RELAY=1 のときは送らない" refused_with_no_relay "https://example.com/"
check "http でも https でもない URL は拒否する" test "$(rc_of mdnew_fetch "example.com" /dev/null)" = 2
check "method の値を検証する" test "$(rc_of mdnew_fetch "https://example.com/" /dev/null nope)" = 2
check "既定の保存先は同じ URL で同じパスになる" \
  test "$(mdnew_default_path https://example.com/a)" = "$(mdnew_default_path https://example.com/a)"
check "既定の保存先は小文字のホスト名とハッシュで決まる" \
  default_path_matches "https://Example.com/a" '/x/markdown-new/example.com-[0-9]*.md'

if [ "${MDNEW_SELFTEST_OFFLINE:-0}" = 1 ]; then
  echo "pass=$pass fail=${fail}（ネットワーク越しの確認は飛ばした）"
  [ "$fail" -eq 0 ]
  exit
fi

work=$(mktemp -d -t mdnew-selftest)
echo "work: $work"

mdnew_fetch_direct "https://blog.cloudflare.com/markdown-for-agents/" "$work/cf.md"
check "Markdown for Agents のサイトは直接取れる" test "$MDNEW_SOURCE" = direct
check "直接取得の本文を保存する" grep -q 'Markdown for Agents' "$work/cf.md"

check "Accept を無視して HTML を返すサイトは直接取得に失敗する" \
  test "$(rc_of mdnew_fetch_direct "https://example.com/" "$work/ex-direct.md")" = 1

mdnew_fetch "https://example.com/" "$work/ex.md" >/dev/null 2>&1
check "直接取れないときは markdown.new に回る" test "$MDNEW_SOURCE" = markdown.new
check "markdown.new の変換方式を拾う" test "$MDNEW_DETAIL" = "Cloudflare Workers AI"
check "markdown.new の本文を保存する" grep -q '^# Example Domain' "$work/ex.md"

# 変換で _ が \_ にエスケープされるため、引数名に _ を使わない。
mdnew_fetch_relay "https://httpbin.org/anything?mdnewprobe=kept" "$work/q.md" >/dev/null 2>&1
check "POST では対象 URL のクエリが保たれる" grep -q 'mdnewprobe' "$work/q.md"

check "markdown.new が変換に失敗したら終了コード 4" \
  test "$(rc_of mdnew_fetch "https://nonexistent-host-zz9.invalid/" "$work/ng.md")" = 4
check "直接取れず送るのを止めたら終了コード 3" \
  test "$(rc_of mdnew_fetch "https://example.com/?token=abc" "$work/tk.md")" = 3
check "失敗したときは保存先を残さない" test ! -e "$work/tk.md"

rm -f -- "$work"/*.md
rmdir -- "$work"
echo "pass=$pass fail=$fail"
[ "$fail" -eq 0 ]
