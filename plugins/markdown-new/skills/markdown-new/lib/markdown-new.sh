#!/usr/bin/env bash
# markdown-new.sh — URL のページを Markdown の全文で取得する関数群。
#
# 提供する関数:
#   mdnew_fetch <url> <out> [method] [retain_images]
#                              対象サイトから直接取り、だめなら markdown.new で変換して out に書く
#   mdnew_fetch_direct <url> <out>
#                              Accept: text/markdown で対象サイトから直接取る
#   mdnew_fetch_relay <url> <out> [method] [retain_images]
#                              markdown.new の POST API で変換して取る
#   mdnew_relay_allowed <url>  markdown.new に送ってよい URL なら 0 を返す。だめなら理由を出して 1 を返す
#   mdnew_default_path <url>   保存先の既定のパスを出力する
#
# 取得の結果は MDNEW_SOURCE（direct か markdown.new）、MDNEW_DETAIL、MDNEW_TOKENS に入る。
# MDNEW_NO_RELAY=1 のときは markdown.new に送らない。
# zsh から直接 source せず、bash -c 'source ...; mdnew_fetch ...' の形で呼ぶ。

# MDNEW_SOURCE などは呼び出し側が読む。
# shellcheck disable=SC2034
set -uo pipefail

MDNEW_API="${MDNEW_API:-https://markdown.new/}"
MDNEW_DIRECT_TIMEOUT="${MDNEW_DIRECT_TIMEOUT:-30}"
MDNEW_RELAY_TIMEOUT="${MDNEW_RELAY_TIMEOUT:-90}"
# markdown.new が対象サイトへ送る Accept と同じ値にする。
MDNEW_ACCEPT='text/markdown, text/html;q=0.9'

MDNEW_SOURCE=""
MDNEW_DETAIL=""
MDNEW_TOKENS=""

_mdnew_err() {
  echo "mdnew: $*" >&2
}

_mdnew_is_web_url() {
  [[ "$1" =~ ^https?://[^/?#]+ ]]
}

_mdnew_host() {
  local a="${1#*://}"
  a="${a%%[/?#]*}"
  a="${a##*@}"
  if [[ "$a" == \[* ]]; then
    printf '%s' "${a%%]*}]"
  else
    printf '%s' "${a%%:*}" | tr '[:upper:]' '[:lower:]'
  fi
}

# 外から届かないホストなら 0 を返す。IPv6 のリテラルはすべてここに含める。
_mdnew_is_private_host() {
  local h="$1"
  case "$h" in
    \[* | localhost | *.localhost | *.local | *.internal | *.lan | *.home.arpa) return 0 ;;
    127.* | 10.* | 192.168.* | 169.254.* | 0.*) return 0 ;;
  esac
  [[ "$h" =~ ^172\.(1[6-9]|2[0-9]|3[01])\. ]] && return 0
  [[ "$h" == *.* ]] || return 0
  return 1
}

# クエリのうち、名前が認証情報らしい引数の名前を 1 行に 1 つ出力する。
_mdnew_secret_params() {
  local url="$1" query name lc pair pairs
  [[ "$url" == *\?* ]] || return 0
  query="${url#*\?}"
  IFS='&' read -ra pairs <<<"$query"
  for pair in "${pairs[@]}"; do
    name="${pair%%=*}"
    lc=$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')
    if [[ "$lc" =~ (^|[_.-])(key|sig|code|sid|auth|session|otp|pwd)$ ]] ||
      [[ "$lc" =~ (token|secret|signature|password|passwd|credential|credentials|apikey|sessionid|jwt)$ ]]; then
      printf '%s\n' "$name"
    fi
  done
}

mdnew_relay_allowed() {
  local url="$1" host authority secrets
  if [ "${MDNEW_NO_RELAY:-0}" = 1 ]; then
    echo "MDNEW_NO_RELAY=1 が指定されている"
    return 1
  fi
  authority="${url#*://}"
  authority="${authority%%[/?#]*}"
  if [[ "$authority" == *@* ]]; then
    echo "URL にユーザー名かパスワードが入っている"
    return 1
  fi
  host=$(_mdnew_host "$url")
  if _mdnew_is_private_host "$host"; then
    echo "$host は外から届かないホストで、markdown.new からは取れない"
    return 1
  fi
  secrets=$(_mdnew_secret_params "$url")
  if [ -n "$secrets" ]; then
    echo "クエリに認証情報らしい引数がある: $(printf '%s' "$secrets" | paste -sd, -)"
    return 1
  fi
  return 0
}

mdnew_default_path() {
  local url="$1" dir host sum
  dir="${MDNEW_OUT_DIR:-${TMPDIR:-/tmp}}"
  host=$(_mdnew_host "$url" | tr -c 'a-z0-9.-' '_')
  sum=$(printf '%s' "$url" | cksum | cut -d' ' -f1)
  printf '%s/markdown-new/%s-%s.md\n' "${dir%/}" "$host" "$sum"
}

mdnew_fetch_direct() {
  local url="$1" out="$2" hdr meta code ctype
  MDNEW_SOURCE="" MDNEW_DETAIL="" MDNEW_TOKENS=""
  hdr=$(mktemp -t mdnew-hdr) || return 1
  if ! meta=$(curl -sS -L --max-time "$MDNEW_DIRECT_TIMEOUT" -H "Accept: $MDNEW_ACCEPT" \
    -D "$hdr" -o "$out" -w '%{http_code}\t%{content_type}' "$url" 2>&1); then
    MDNEW_DETAIL="curl が失敗した: $meta"
    rm -f -- "$hdr" "$out"
    return 1
  fi
  code="${meta%%$'\t'*}"
  ctype=$(printf '%s' "${meta#*$'\t'}" | tr '[:upper:]' '[:lower:]')
  # Accept を無視して HTML を 200 で返すサイトが多いので、状態コードではなく Content-Type で判定する。
  if [[ "$code" != 2?? ]] || [[ "$ctype" != text/markdown* ]] || [ ! -s "$out" ]; then
    MDNEW_DETAIL="HTTP ${code}、Content-Type: ${ctype:-なし}"
    rm -f -- "$hdr" "$out"
    return 1
  fi
  MDNEW_SOURCE="direct"
  MDNEW_DETAIL="対象サイトが Markdown を返した"
  # Cloudflare のブログは x-markdown-tokens を付けると書いているが、実際には付かないことがある。
  MDNEW_TOKENS=$(grep -i '^x-markdown-tokens:' "$hdr" | tail -n 1 | tr -d '\r' | awk '{print $2}')
  rm -f -- "$hdr"
  return 0
}

mdnew_fetch_relay() {
  local url="$1" out="$2" method="${3:-auto}" images="${4:-false}" body resp code
  MDNEW_SOURCE="" MDNEW_DETAIL="" MDNEW_TOKENS=""
  body=$(jq -n --arg url "$url" --arg method "$method" --argjson images "$images" \
    '{url: $url, method: $method, retain_images: $images}') || return 2
  resp=$(mktemp -t mdnew-resp) || return 1
  # GET の https://markdown.new/<url> は対象 URL のクエリを落とすので、POST で送る。
  if ! code=$(curl -sS --max-time "$MDNEW_RELAY_TIMEOUT" "$MDNEW_API" \
    -H 'Content-Type: application/json' -d "$body" -o "$resp" -w '%{http_code}' 2>&1); then
    MDNEW_DETAIL="curl が失敗した: $code"
    rm -f -- "$resp"
    return 4
  fi
  if [ "$code" = 429 ]; then
    MDNEW_DETAIL="markdown.new のレート制限（IP ごとに 1 日 500 回）に達した"
    rm -f -- "$resp"
    return 5
  fi
  if [ "$code" != 200 ] || [ "$(jq -r '.success' "$resp" 2>/dev/null)" != true ]; then
    MDNEW_DETAIL="markdown.new が HTTP $code を返した: $(jq -r '.error // empty' "$resp" 2>/dev/null | head -c 300)"
    rm -f -- "$resp"
    return 4
  fi
  jq -r '.content // empty' "$resp" >"$out"
  if [ ! -s "$out" ]; then
    MDNEW_DETAIL="markdown.new の応答に本文が無かった"
    rm -f -- "$resp" "$out"
    return 4
  fi
  MDNEW_SOURCE="markdown.new"
  MDNEW_DETAIL=$(jq -r '.method // empty' "$resp")
  MDNEW_TOKENS=$(jq -r '.tokens // empty' "$resp")
  rm -f -- "$resp"
  return 0
}

mdnew_fetch() {
  local url="$1" out="$2" method="${3:-auto}" images="${4:-false}" reason direct_detail="" rc
  if ! _mdnew_is_web_url "$url"; then
    _mdnew_err "http:// か https:// で始まる URL を渡す: $url"
    return 2
  fi
  case "$method" in auto | ai | browser) ;; *)
    _mdnew_err "method は auto・ai・browser のどれか: $method"
    return 2
    ;;
  esac
  case "$images" in true | false) ;; *)
    _mdnew_err "retain_images は true か false: $images"
    return 2
    ;;
  esac
  # フラグメントはどのサーバーにも送らない。#access_token= のような値を外に出さないために落とす。
  url="${url%%#*}"
  mkdir -p -- "$(dirname -- "$out")" || return 1

  # method を指定したときは markdown.new の変換方式を使いたいときなので、直接取得を飛ばす。
  if [ "$method" = auto ]; then
    mdnew_fetch_direct "$url" "$out" && return 0
    direct_detail="$MDNEW_DETAIL"
  else
    direct_detail="method=$method の指定で直接取得を飛ばした"
  fi

  if ! reason=$(mdnew_relay_allowed "$url"); then
    _mdnew_err "直接は取れなかった（${direct_detail}）。markdown.new には送らない: $reason"
    return 3
  fi
  mdnew_fetch_relay "$url" "$out" "$method" "$images"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    _mdnew_err "直接は取れなかった（${direct_detail}）。markdown.new でも取れなかった（${MDNEW_DETAIL}）"
  fi
  return "$rc"
}
