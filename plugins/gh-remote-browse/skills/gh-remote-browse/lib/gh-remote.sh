#!/usr/bin/env bash
# gh-remote.sh — リポジトリをクローンせずに中身を読むための関数群。
#
# gh の `gh repo read-file` と `gh repo read-dir`（どちらも preview）と、
# 再帰列挙のための git trees API をまとめている。
#
# 提供する関数:
#   ghr_check_deps                             依存コマンドと認証を検証する
#   ghr_file <repo> <path> [ref]               ファイル内容を stdout に出す
#   ghr_save <repo> <path> <dest> [ref]        ファイルをディスクに書く
#   ghr_dir  <repo> [path] [ref]               1 階層を type/path/size のタブ区切りで出す
#   ghr_tree <repo> [prefix] [ref]             再帰列挙を type/path のタブ区切りで出す
#   ghr_grep <repo> <pattern> [prefix] [ref]   リモートのファイルを横断して検索する
#   ghr_many <repo> <dest_dir> <ref> <path...> 複数ファイルをまとめて取得する
#
# repo は OWNER/REPO 形式。ref を省略すると既定ブランチ、ghr_tree と ghr_grep では
# HEAD を読む。依存コマンドは gh、jq、awk、grep、tr。
#
# 移植性のための制約が 2 つある。
# 1. source される前提のため set や shopt で呼び出し側のシェルオプションを変えない。
# 2. 変数名に path を使わない。zsh では path が PATH と連動する特殊変数で、
#    関数内で local path=... と書くだけでその関数の PATH が壊れ、
#    gh すら command not found になる。cdpath fpath manpath status argv も同様に避ける。

# gh はページャを持つ。端末に直接出力すると read-file がページャに入って
# 自動実行が止まる。ただし GH_PAGER を export すると source した呼び出し側の
# シェルに残り、無関係な gh コマンドからもページャが消える。
# そのため呼び出しごとに前置して渡す。
_ghr_gh() {
  GH_PAGER=cat gh "$@"
}

# 端末制御文字を落とす。タブ (011) と改行 (012) は残す。
# リモートの内容を人の端末へ流す経路では必ず通す。
_ghr_strip_ctrl() {
  LC_ALL=C tr -d '\000-\010\013\014\016-\037\177'
}

# 依存コマンドと gh の認証状態を検証する。満たない場合は理由を stderr に出す。
ghr_check_deps() {
  local missing="" c=""
  for c in gh jq awk grep tr; do
    command -v "$c" >/dev/null 2>&1 || missing="$missing $c"
  done
  if [ -n "$missing" ]; then
    printf 'error: 必要なコマンドがない:%s\n' "$missing" >&2
    return 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    printf 'error: gh が認証されていない。gh auth login を実行する\n' >&2
    return 1
  fi
  return 0
}

# ファイル内容をそのまま出す。
# --allow-escape-sequences を付けている。既定ではエスケープシーケンスを含む
# ファイルの出力を拒否して非ゼロで終わり、機械処理では通らないため。
# この関数の出力を人の端末へ流す場合は _ghr_strip_ctrl を通すこと。
ghr_file() {
  local repo="$1" fpath_="$2" ref="${3:-}"
  if [ -n "$ref" ]; then
    _ghr_gh repo read-file "$fpath_" --repo "$repo" --allow-escape-sequences --ref "$ref"
  else
    _ghr_gh repo read-file "$fpath_" --repo "$repo" --allow-escape-sequences
  fi
}

# ディスクに書く。--output は内容チェックを適用せず生バイトを書く。
ghr_save() {
  local repo="$1" fpath_="$2" dest="$3" ref="${4:-}"
  mkdir -p "$(dirname "$dest")" || return 1
  if [ -n "$ref" ]; then
    _ghr_gh repo read-file "$fpath_" --repo "$repo" --output "$dest" --clobber --ref "$ref"
  else
    _ghr_gh repo read-file "$fpath_" --repo "$repo" --output "$dest" --clobber
  fi
}

# 1 階層だけを列挙する。
# read-dir --json は結果を {entries: [...]} で包むため、そのままでは
# 配列として扱えない。ここで平坦なタブ区切りに直す。
#
# gh の出力を一度変数に受けてから jq に渡す。gh | jq と直接つなぐと
# パイプラインの終了ステータスが jq のものになり、gh の失敗が 0 で隠れて
# 存在しないパスと空ディレクトリを呼び出し側から区別できなくなる。
ghr_dir() {
  local repo="$1" dpath_="${2:-}" ref="${3:-}" out=""
  if [ -n "$dpath_" ] && [ -n "$ref" ]; then
    out=$(_ghr_gh repo read-dir "$dpath_" --repo "$repo" --ref "$ref" --json name,path,type,size) || return 1
  elif [ -n "$dpath_" ]; then
    out=$(_ghr_gh repo read-dir "$dpath_" --repo "$repo" --json name,path,type,size) || return 1
  elif [ -n "$ref" ]; then
    out=$(_ghr_gh repo read-dir --repo "$repo" --ref "$ref" --json name,path,type,size) || return 1
  else
    out=$(_ghr_gh repo read-dir --repo "$repo" --json name,path,type,size) || return 1
  fi
  printf '%s' "$out" | jq -r '.entries[] | "\(.type)\t\(.path)\t\(.size)"'
}

# 再帰列挙する。read-dir は 1 階層しか返さないため階層ごとに呼ぶと
# ディレクトリ数だけ API を叩く。git trees API なら 1 リクエストで全体が取れる。
# 巨大リポジトリでは応答が打ち切られるため truncated を検出して警告する。
ghr_tree() {
  local repo="$1" prefix="${2:-}" ref="${3:-HEAD}" out=""
  out=$(_ghr_gh api "repos/$repo/git/trees/$ref?recursive=1") || return 1
  if [ "$(printf '%s' "$out" | jq -r '.truncated')" = "true" ]; then
    printf 'warning: trees API の応答が打ち切られた。prefix を絞って ghr_dir を使う\n' >&2
  fi
  printf '%s' "$out" | jq -r --arg p "$prefix" '
    .tree[] | select($p == "" or (.path | startswith($p))) | "\(.type)\t\(.path)"
  '
}

# リモートのファイルを横断して検索する。
# ファイル 1 件ごとに API を 1 回叩くため prefix で必ず絞る。
# 既定の上限は 40 ファイル。超えた分は件数を報告して読まない。
# 打ち切りを黙って隠すと検索結果が全体だと誤解されるため必ず表示する。
#
# ghr_tree の結果を一度変数に受けてから awk に渡す。ghr_tree | awk と
# 直接つなぐと終了ステータスが awk のものになり、入力 0 件でも awk が 0 で
# 終わるため、存在しないリポジトリでも成功かつ無出力になってしまう。
#
# 一致行は _ghr_strip_ctrl を通す。ghr_file は --allow-escape-sequences 付きで
# 生の内容を返し、grep はエスケープシーケンスを除去しないため、
# そのまま出すと悪意あるファイル内容が端末に届く。
ghr_grep() {
  local repo="$1" pattern="$2" prefix="${3:-}" ref="${4:-HEAD}"
  local limit="${GHR_GREP_LIMIT:-40}" tree_out="" list="" total=0
  tree_out=$(ghr_tree "$repo" "$prefix" "$ref") || return 1
  list=$(printf '%s\n' "$tree_out" | awk -F'\t' '$1=="blob"{print $2}')
  total=$(printf '%s\n' "$list" | grep -c . || true)
  if [ "$total" -eq 0 ]; then
    printf 'notice: 対象ファイルが 0 件だった\n' >&2
    return 0
  fi
  if [ "$total" -gt "$limit" ]; then
    printf 'notice: 対象 %s 件のうち先頭 %s 件だけを検索する。GHR_GREP_LIMIT で変更する\n' \
      "$total" "$limit" >&2
    list=$(printf '%s\n' "$list" | head -n "$limit")
  fi
  local fail_tmp status=0
  fail_tmp=$(mktemp)
  printf '%s\n' "$list" | while IFS= read -r one; do
    [ -n "$one" ] || continue
    local content grep_rc
    if ! content=$(ghr_file "$repo" "$one" "$ref" 2>/dev/null); then
      printf 'warning: %s の取得に失敗した\n' "$one" >&2
      printf '%s\n' "$one" >> "$fail_tmp"
      continue
    fi
    printf '%s' "$content" | grep -nH --label="$one" -e "$pattern" | _ghr_strip_ctrl
    grep_rc=${PIPESTATUS[0]}
    # grep の「一致なし」(exit 1) は正常。ghr_file の失敗や grep の実行時エラー(exit >1)だけ報告する。
    if [ "$grep_rc" -gt 1 ]; then
      printf 'warning: %s の検索でエラーが発生した(grep exit %s)\n' "$one" "$grep_rc" >&2
      printf '%s\n' "$one" >> "$fail_tmp"
    fi
  done
  if [ -s "$fail_tmp" ]; then
    printf 'warning: 読み取れなかった、または検索に失敗したファイルがある。詳細は上記の warning を参照\n' >&2
    status=1
  fi
  rm -f "$fail_tmp"
  return "$status"
}

# 複数ファイルをまとめて取得する。取得できたものはローカルのパスを stdout に出す。
#
# dest_dir の外へ書き出すパスは拒否する。リモートのパスをそのまま連結すると、
# 絶対パスや .. を含むパスで dest_dir 外の既存ファイルを警告なく上書きできる。
# 判定は厳しめにしていて、a..b のような正当な名前も弾く。
ghr_many() {
  local repo="$1" dest_dir="$2" ref="$3" one=""
  shift 3
  for one in "$@"; do
    case "$one" in
      /*|*..*|"")
        printf 'warning: dest_dir の外を指しうるパスを拒否した: %s\n' "$one" >&2
        continue
        ;;
    esac
    if ghr_save "$repo" "$one" "$dest_dir/$one" "$ref" >/dev/null; then
      printf '%s\n' "$dest_dir/$one"
    else
      printf 'warning: 取得できなかった: %s\n' "$one" >&2
    fi
  done
}
