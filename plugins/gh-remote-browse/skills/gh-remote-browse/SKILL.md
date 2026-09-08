---
name: gh-remote-browse
description: リポジトリをクローンせずにリモートのファイル内容とディレクトリ構成を読む。gh repo read-file と gh repo read-dir と git trees API をまとめたシェル関数群。他リポジトリのコードを参照したいとき、特定のブランチやタグやコミットの内容を確認したいとき、クローンする価値のない一時的な調査をするときに使う。
allowed-tools: Bash(gh repo read-file *) Bash(gh repo read-dir *) Bash(gh api *) Bash(jq *)
---

# gh-remote-browse

`gh repo read-file` と `gh repo read-dir` を使うと、クローンせずにリモートの内容を読める。この 2 つはどちらも preview 扱いで、単体だと 1 階層しか辿れず、ページャとエスケープシーケンスの落とし穴もある。それらをまとめたのがこのスキル。

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/gh-remote-browse/lib/gh-remote.sh
```

`bash` と `zsh` のどちらから source しても動く。

## 前提条件

依存する外部コマンドは `gh`、`jq`、`awk`、`grep`、`tr`。`gh` は認証済みである必要がある。

```bash
ghr_check_deps    # 不足しているコマンドと未認証を検出して理由を stderr に出す
```

`jq` がないと `ghr_dir` の結果が空になり、ディレクトリが空だったのか判別できない。先に `ghr_check_deps` を通すこと。

## 関数

| 関数 | 役割 |
|---|---|
| `ghr_check_deps` | 依存コマンドと `gh` の認証状態を検証する |
| `ghr_file <repo> <path> [ref]` | ファイル内容を stdout に出す |
| `ghr_save <repo> <path> <dest> [ref]` | ファイルをディスクに書く |
| `ghr_dir <repo> [path] [ref]` | 1 階層を type、path、size のタブ区切りで出す |
| `ghr_tree <repo> [prefix] [ref]` | 再帰列挙を type、path のタブ区切りで出す |
| `ghr_grep <repo> <pattern> [prefix] [ref]` | リモートのファイルを横断して検索する |
| `ghr_many <repo> <dest_dir> <ref> <path...>` | 複数ファイルをまとめて取得する |

`repo` は `OWNER/REPO` 形式。`ref` はブランチ、タグ、コミットのいずれでもよい。省略すると `ghr_file` と `ghr_dir` と `ghr_save` は既定ブランチ、`ghr_tree` と `ghr_grep` は `HEAD` を読む。

## 使い方

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/gh-remote-browse/lib/gh-remote.sh

# 他リポジトリのファイルを読む
ghr_file cli/cli README.md

# タグを指定して読む
ghr_file cli/cli README.md v2.50.0

# 構成を再帰的に把握する
ghr_tree owner/repo apps/api/src main

# リモートを横断検索する
ghr_grep owner/repo 'createServer' apps/api/src main

# 手元に落として編集や差分に使う
ghr_many owner/repo /tmp/snapshot main package.json tsconfig.json
```

素の `gh` を直接使ってもよい。この 2 コマンドの最小形は次のとおり。

```bash
gh repo read-file <path> --repo OWNER/REPO [--ref REF] [--output PATH]
gh repo read-dir [<path>] --repo OWNER/REPO [--ref REF] [--json name,path,type,size]
```

## 実測で分かった落とし穴

どちらのコマンドも preview 扱いで、仕様が予告なく変わる可能性が明記されている。壊れたらまず `gh repo read-file --help` で現在のフラグを確認する。

`read-file` は TTY 判定でページャに入る。自動実行の途中で止まるため、ライブラリは `gh` の呼び出しごとに `GH_PAGER=cat` を前置している。export はしない。export すると source した呼び出し側のシェルに残り、無関係な `gh` コマンドからもページャが消えてしまう。素の `gh` を自分で呼ぶときは同じ前置が必要になる。

`gh | jq` のように直接つなぐと、パイプラインの終了ステータスが後段のものになり `gh` の失敗が 0 で隠れる。存在しないパスと空ディレクトリを呼び出し側から区別できなくなるため、ライブラリは `gh` の出力を一度変数に受けてから後段へ渡している。`ghr_tree | awk` も同様で、入力 0 件でも `awk` は 0 で終わる。

`ghr_grep` の一致行は端末制御文字を落としてから出力する。`ghr_file` は `--allow-escape-sequences` 付きで生の内容を返し、`grep` はエスケープシーケンスを除去しないため、素通しするとリモートのファイル内容が端末を操作できてしまう。

`ghr_many` は `dest_dir` の外を指しうるパスを拒否する。リモートのパスをそのまま連結すると、絶対パスや `..` を含むパスで `dest_dir` 外の既存ファイルを警告なく上書きできる。判定は厳しめで、`a..b` のような正当な名前も弾く。

`read-file` は既定でエスケープシーケンスを含むファイルの出力を拒否し、非ゼロで終わる。端末を操作されるのを防ぐためで、機械処理では通らないと困るので `ghr_file` は `--allow-escape-sequences` を付けている。人の端末へそのまま流す用途では付けない。`--output` でディスクに書く場合はこのチェックが適用されず、常に生バイトが書かれる。

`read-dir` は 1 階層しか返さない。階層ごとに呼ぶとディレクトリ数だけ API を叩くため、再帰列挙には `repos/O/R/git/trees/<ref>?recursive=1` を使う。1 リクエストで全体が取れる。巨大リポジトリでは応答が打ち切られるため、`ghr_tree` は `truncated` を検出して警告する。打ち切られたら prefix を絞って `ghr_dir` に切り替える。

`read-dir --json` の結果は `{entries: [...]}` で包まれる。`.[]` ではなく `.entries[]` で辿る。

`read-dir` の既定出力はヘッダなしのタブ区切りで、列は type、name、modeOctal、size の順。symlink は type が `symlink` になり、モードは `120000` で出る。

存在しないパスは終了コード 1 と `HTTP 404` になる。private リポジトリも認証が通っていれば読める。

`ghr_grep` はファイル 1 件ごとに API を 1 回叩く。既定の上限は 40 ファイルで、超えた場合は件数を stderr に報告してから打ち切る。上限を変えるには `GHR_GREP_LIMIT` を設定する。

## zsh で source する場合の注意

シェル関数の中で `path` という変数名を使ってはいけない。zsh では `path` が `PATH` と連動する配列で、`local path=...` と書くだけでその関数内の `PATH` が壊れ、`gh` すら `command not found` になる。`cdpath`、`fpath`、`manpath`、`status`、`argv` も同様に避ける。このライブラリは `fpath_` や `dpath_` のように接尾辞を付けて回避している。

このファイルは source される前提のため、`set` や `shopt` で呼び出し側のシェルオプションを変更しない。

## いつクローンするか

差分を取る、履歴を辿る、ビルドする、多数のファイルを繰り返し読む場合はクローンしたほうが速い。このスキルが向くのは、数ファイルの内容を確認する、構成を把握する、特定の ref での状態を見る、といった読み捨ての調査である。
