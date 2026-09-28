#!/usr/bin/env bash
# review-guard.sh — PR にインラインコメントを投稿する前の検証をまとめた関数群。
#
# 提供する関数:
#   guard_valid_lines <repo> <pr>              差分に実在する行番号の集合を JSON で返す
#   guard_existing_keys <repo> <pr>            既存コメントの識別キーを行区切りで返す
#   guard_annotate <comments_json> <valid_json> <keys_file>
#                                              各コメントに line_ok と dup を付けて返す
#   guard_post_review <repo> <pr> <body> <comments_json>
#                                              レビューを COMMENT イベントで投稿する
#
# コメントの JSON は少なくとも path と line と body を持つオブジェクトの配列にする。

set -uo pipefail

# 差分の追加側と文脈行に実在する行番号だけを許可する。
# 行番号がずれたインラインコメントはレビュイーに届かず、
# 指摘全体をやり直すことになるため投稿前に落とす。
guard_valid_lines() {
  local repo="$1" pr="$2"
  gh api --paginate --slurp "repos/$repo/pulls/$pr/files" 2>/dev/null | jq '
    def hunk_lines:
      (.patch // "") | split("\n")
      | reduce .[] as $l ({cur:0, out:[]};
          if ($l | test("^@@")) then
            .cur = (($l | capture("\\+(?<s>[0-9]+)") | .s | tonumber) - 1)
          elif ($l | startswith("-")) then .
          elif ($l | startswith("\\")) then .
          else .cur += 1 | .out += [.cur]
          end)
      | .out;
    [ (.. | objects | select(has("filename")) ) | {key: .filename, value: hunk_lines} ]
    | from_entries
  '
}

# 既存コメントの識別キーを path と line で作る。第 3 引数の login で著者を絞り、
# 省略時は認証ユーザー自身のコメントだけを対象にする。
# 並列エージェントが同じ箇所へ重複投稿するのを防ぐため、書き込み直前に取得して使う。
#
# 本文の先頭数十文字で一致を取る方式は使わない。先頭が偶然一致した別の指摘を
# 重複と誤判定し、投稿対象から黙って落としてしまうため。位置と著者で判定すると
# 判定基準が予測可能になる。代償として、自分がすでにコメントした行に対する
# 2 件目の別の指摘も抑止される。1 行に複数の指摘を出す運用では login を
# 存在しない値にして無効化する。
guard_existing_keys() {
  local repo="$1" pr="$2" login="${3:-}"
  [ -n "$login" ] || login=$(gh api user --jq .login 2>/dev/null) || login=""
  gh api --paginate --slurp "repos/$repo/pulls/$pr/comments" 2>/dev/null | jq -r --arg me "$login" '
    [ (.. | objects | select(has("path")) ) ]
    | .[]
    | select($me == "" or (.user.login // "") == $me)
    | "\(.path)\t\(.line // .original_line)"
  '
}

# 各コメントに line_ok と dup を付けて返す。呼び出し側が投稿対象と除外対象に分ける。
guard_annotate() {
  local comments="$1" valid="$2" keys_file="$3"
  jq -n --argjson comments "$comments" --argjson valid "$valid" --rawfile ex "$keys_file" '
    ($ex | split("\n") | map(select(length > 0))) as $keys
    | [ $comments[]
        | . as $c
        | ($valid[$c.path] // []) as $ok
        | $c + {
            line_ok: (($ok | index($c.line)) != null),
            dup: (($keys | index("\($c.path)\t\($c.line)")) != null)
          }
      ]
  '
}

# レビューを投稿する。body に suggestion ブロックを含めず、
# 修正案はインラインコメント側にだけ入れる規約に合わせている。
# 第 5 引数 event は省略可（既定 COMMENT）。APPROVE / REQUEST_CHANGES / COMMENT を渡せる。
# GitHub は comments が 1 件以上ある場合 APPROVE イベントを拒否するため、
# 呼び出し側は「投稿するインラインコメントが 0 件のときだけ APPROVE を渡す」こと。
guard_post_review() {
  local repo="$1" pr="$2" body="$3" comments="$4" event="${5:-COMMENT}"
  jq -n --arg body "$body" --arg event "$event" --argjson comments "$comments" '{
    body: $body,
    event: $event,
    comments: [ $comments[] | {path, line, side: "RIGHT", body} ]
  }' | gh api -X POST "repos/$repo/pulls/$pr/reviews" --input - >/dev/null
}
