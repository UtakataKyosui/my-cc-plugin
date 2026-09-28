---
name: gh-review-guard
description: PR にインラインコメントを投稿する前に、行番号が差分に実在するかを検証し、同じ箇所への重複投稿を防ぐシェル関数群。gh pr review や pulls/N/reviews へ自動でコメントを投稿するスクリプトを書くとき、行番号ずれで指摘をやり直したくないとき、並列エージェントが同一 PR に書き込むときに使う。
allowed-tools: Bash(gh pr diff *) Bash(gh pr view *) Bash(gh api *) Bash(jq *)
---

# gh-review-guard

手動実行時は `${CLAUDE_PLUGIN_ROOT}` が未設定なので、`claude plugin list` で確認するか `~/.claude/plugins/cache/my-cc-plugin/herdr-orchestration/<version>/` に置き換えて実行する。

PR へインラインコメントを投稿するスクリプトが、毎回同じ2つの理由で失敗する。行番号が差分に載っておらずコメントがレビュイーに届かない場合と、同じ箇所に重複して投稿してしまう場合である。その2つを投稿前に潰す。

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/gh-review-guard/lib/review-guard.sh
```

## 関数

| 関数 | 役割 |
|---|---|
| `guard_valid_lines <repo> <pr>` | 差分の追加側と文脈行に実在する行番号を `{path: [line...]}` で返す |
| `guard_existing_keys <repo> <pr> [login]` | 指定著者の既存コメントの `path` と `line` を行区切りで返す。login 省略時は認証ユーザー |
| `guard_annotate <comments_json> <valid_json> <keys_file>` | 各コメントに `line_ok` と `dup` を付けて返す |
| `guard_post_review <repo> <pr> <body> <comments_json>` | レビューを COMMENT イベントで投稿する |

コメントの JSON は `path` と `line` と `body` を持つオブジェクトの配列にする。

## 使い方の型

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/gh-review-guard/lib/review-guard.sh

REPO=owner/repo
PR=123
COMMENTS='[{"path":"src/a.ts","line":42,"body":"ここで null になる"}]'

valid=$(guard_valid_lines "$REPO" "$PR")
guard_existing_keys "$REPO" "$PR" >/tmp/keys.txt

annotated=$(guard_annotate "$COMMENTS" "$valid" /tmp/keys.txt)
postable=$(jq '[.[] | select(.line_ok and (.dup | not))]' <<<"$annotated")
dropped=$(jq '[.[] | select((.line_ok | not) or .dup)]' <<<"$annotated")

jq -r '.[] | "除外 \(.path):\(.line) 理由=\(if (.line_ok|not) then "行番号が差分に存在しない" else "重複" end)"' <<<"$dropped"

guard_post_review "$REPO" "$PR" "$BODY" "$postable"
```

`guard_existing_keys` は投稿の直前に取得する。並列に走る別のエージェントが先に書き込んでいる可能性があるため、事前にまとめて取得したものを使い回さない。

## 重複判定の基準

同じ `path` と `line` に自分がすでにコメントしている場合を重複とみなす。本文の先頭数十文字で一致を取る方式は使わない。先頭が偶然一致した別の指摘を重複と誤判定し、投稿対象から黙って落としてしまうためである。

代償として、自分がすでにコメントした行に対する 2 件目の別の指摘も抑止される。1 行に複数の指摘を出す運用では、第 3 引数に存在しない login を渡して無効化する。

## 前提にしている規約

レビュー本文に suggestion ブロックを入れない。修正案はインラインコメント側にだけ含める。`guard_post_review` は本文をそのまま送るため、この分離は呼び出し側で守る。

行番号は追加側の行を指す。`side: "RIGHT"` を固定で送っている。削除された行に対してコメントする用途には対応していない。

## 除外の判定基準

`guard_valid_lines` は `pulls/N/files` の patch を解析し、`@@` ヘッダの追加側開始行から、追加行と文脈行だけを数え上げる。削除行と `\ No newline at end of file` は数えない。この集合に載らない行番号は投稿しても差分上に表示されないため落とす。

## 使っているスキル

- `pr-adversarial-review` — 敵対的レビューの投稿段で使う
