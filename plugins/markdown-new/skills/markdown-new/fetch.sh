#!/usr/bin/env bash
# fetch.sh — URL のページを Markdown の全文で取得してファイルに保存し、保存先と取得元を表示する。

set -uo pipefail
# shellcheck source=SCRIPTDIR/lib/markdown-new.sh
source "${MDNEW_LIB:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/markdown-new.sh}"

usage() {
  cat <<'EOF'
使い方: fetch.sh [--method auto|ai|browser] [--images] [--no-relay] [--out <path>] <url>

  --method    auto は直接取得を試してから markdown.new に回す。ai と browser は markdown.new の変換方式を指定する
  --images    markdown.new の変換結果に画像を残す
  --no-relay  markdown.new に送らず、対象サイトから直接取れたときだけ保存する
  --out       保存先。省略すると $TMPDIR/markdown-new/ の下に書く
EOF
}

method=auto
images=false
out=""
while [ $# -gt 0 ]; do
  case "$1" in
    --method)
      method="${2:-}"
      shift 2 || { usage >&2; exit 2; }
      ;;
    --images)
      images=true
      shift
      ;;
    --no-relay)
      export MDNEW_NO_RELAY=1
      shift
      ;;
    --out)
      out="${2:-}"
      shift 2 || { usage >&2; exit 2; }
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*)
      echo "fetch.sh: 知らないオプション: $1" >&2
      usage >&2
      exit 2
      ;;
    *) break ;;
  esac
done
if [ $# -ne 1 ]; then
  usage >&2
  exit 2
fi

url="$1"
[ -n "$out" ] || out=$(mdnew_default_path "$url")
mdnew_fetch "$url" "$out" "$method" "$images" || exit $?

printf 'path: %s\n' "$out"
printf 'source: %s（%s）\n' "$MDNEW_SOURCE" "$MDNEW_DETAIL"
printf 'lines: %s\n' "$(wc -l <"$out" | tr -d ' ')"
printf 'bytes: %s\n' "$(wc -c <"$out" | tr -d ' ')"
printf 'tokens: %s\n' "${MDNEW_TOKENS:-不明}"
