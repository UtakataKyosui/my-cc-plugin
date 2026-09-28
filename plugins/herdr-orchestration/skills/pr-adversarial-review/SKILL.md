---
name: pr-adversarial-review
description: 複数 PR を herdr のペイン上で並列に敵対的レビューし、検証を通過した指摘だけを PR へ投稿する。スコープ外の指摘は Follow Up Issue にするか、切り出し案として表示するだけにする。gh と herdr と jq があればリポジトリを問わず動く。
when_to_use: 「複数の PR をまとめてレビューして」「敵対的レビューをして」「レビュー依頼されている PR をレビューして」「PR をレビューして Follow Up Issue を作って」と指示されたとき。PR 番号を指定しない場合は自分宛のレビュー依頼を自動で収集する。
argument-hint: "[pr-number ...]"
allowed-tools: Bash(herdr *) Bash(jq *) Bash(gh pr view *) Bash(gh pr diff *) Bash(gh pr review *) Bash(gh search prs *) Bash(gh api *) Bash(gh issue create *)
---

# pr-adversarial-review

手動実行時は `${CLAUDE_PLUGIN_ROOT}` が未設定なので、`claude plugin list` で確認するか `~/.claude/plugins/cache/my-cc-plugin/herdr-orchestration/<version>/` に置き換えて実行する。

複数 PR のレビューを、Dynamic Workflow と同じ pipeline 構造で herdr のペイン上に展開する。PR ごとに次の3段を独立に流すため、PR A の検証中に PR B のレビューが走る。

```
PR ごと: Review(レビュワー, sonnet high) -> Verify(反証者, opus xhigh) -> Plan(振り分け)
        ↓
     collect.sh が plans.json と plan.md と timing.jsonl を書く
        ↓
     ユーザー承認（ここは必ず人が判断する）
        ↓
     post.sh --confirmed が投稿と Issue 作成(方針に応じて)を行う
```

指摘は必ず反証者を通す。1 人目が出した指摘を 2 人目が壊しにいき、壊せなかったものだけが投稿対象になる。判断に迷った指摘は反証側に分類され、投稿されない。

このスキルはかつて `pr-adversarial-review`(複数 PR 指定、Issue 自動作成)と `review-requested-adversarial`(レビュー依頼 PR 自動収集、提案のみ)に分かれていた。レビュワーと反証者の起動ロジックがほぼ同一だったため統合し、差異は `--discover` と `--issue-policy` のフラグで表す。

## 前提条件

- `herdr-fanout` スキルがあること。ペイン展開の共通処理は `${CLAUDE_PLUGIN_ROOT}/skills/herdr-fanout/lib/flow.sh` にあり、collect.sh がそれを source する。別の場所に置く場合は `HERDR_FANOUT_LIB` で指定する
- `agent-routing` スキルがあること。ロール別のモデル・effort・ツール権限は `${CLAUDE_PLUGIN_ROOT}/skills/agent-routing/lib/routing.sh` にあり、collect.sh がそれを source する。別の場所に置く場合は `AGENT_ROUTING_LIB` で指定する
- `gh-review-guard` スキルがあること。投稿前の行番号検証と重複検出は `${CLAUDE_PLUGIN_ROOT}/skills/gh-review-guard/lib/review-guard.sh` にあり、post.sh がそれを source する。別の場所に置く場合は `GH_REVIEW_GUARD_LIB` で指定する
- herdr のペイン内で動いていること。`HERDR_ENV=1` でない場合は実行しない
- `gh`、`jq`、`herdr` が PATH にあること
- `herdr integration status` で対象エージェント種別のフックが current であること。claude 以外を使う場合は `herdr integration install <kind>` を先に実行する
- レビュー依頼 PR の自動収集(`--discover review-requested`)には `gh wheel` 拡張があるとよい。なければ `gh my-task`、それもなければ `gh search prs --review-requested @me` にフォールバックする

## 実行手順

### Step 0: ワークスペースを用意する

`flow_workspace_create` で専用のワークスペースを作り、レビューのタブをそこへ置く。利用者の作業タブと混ざらず、中を見るのに一段深い操作が要る。command substitution では呼ばず、呼んだあとに `$FLOW_WORKSPACE` を読む。

レビュワーと反証者が利用者へ質問したい場合は、`skills/herdr-fanout` の質問の中継を使う。ペイン側は AskUserQuestion を禁止されているため、質問はファイルへ書かれ、メインのセッションが利用者に聞いて回答を書き戻す。

### Step 1: 対象 PR を決めて収集する

カレントディレクトリは対象リポジトリのルートにする。

PR 番号を渡すと、その PR だけを対象にする(`--discover args` と同じ)。

```bash
${CLAUDE_PLUGIN_ROOT}/skills/pr-adversarial-review/collect.sh 123 124 125
```

PR 番号を省略すると、自分宛のレビュー依頼 PR(ドラフト除く)を自動収集する(`--discover review-requested` と同じ)。

```bash
${CLAUDE_PLUGIN_ROOT}/skills/pr-adversarial-review/collect.sh -R owner/repo -j 3
```

主なオプション。

| オプション | 意味 |
|---|---|
| `-R owner/repo` | 対象リポジトリ。省略時は cwd から検出 |
| `--kind <kind>` | 使うエージェント種別(herdr の `--kind`)。既定は claude |
| `-j N` | 同時に走らせる PR 数。既定は 3 |
| `--keep-panes` | 終了後もタブを閉じない。デバッグ用 |
| `--discover args\|review-requested` | PR の収集方法を明示する。省略時は PR 番号の有無から推測する |
| `--issue-policy create\|suggest` | スコープ外の指摘の扱い。既定は `suggest`(提案のみ、Issue は自動作成しない) |

自分の PR ではなく他人の PR をレビューするとき、スコープ外の指摘から無断で Issue を作ると混乱を招くため、既定は安全側の `suggest` にしている。自分が対応方針まで決めてよい複数 PR の一括レビューでは `--issue-policy create` を明示する。

環境変数で挙動を変えられる。`PRAR_OUT_DIR` は出力先、`PRAR_TIMEOUT_MS` は 1 エージェントあたりの待ち時間。エージェントに渡す引数はロールごとに `skills/agent-routing` が決めるため、このスキル単体の環境変数では上書きしない。ロール別に上書きしたい場合は `AGENT_ROUTE_MODEL_REVIEW` のような `skills/agent-routing/SKILL.md` に書かれた変数を使う。

collect.sh は最後に出力ディレクトリのパスを stdout に返す。GitHub への書き込みは一切しない。

### Step 2: 起案内容を読んでユーザーに確認する

```bash
cat <RUN_DIR>/plan.md
${CLAUDE_PLUGIN_ROOT}/skills/pr-adversarial-review/post.sh <RUN_DIR>
```

`post.sh` を `--confirmed` なしで実行すると、投稿予定のレビュー本文、インラインコメント、out_of_scope の扱い(方針に応じて Issue 予定 or 提案のみ)の全文を表示して終わる。行番号が差分に載っていないコメントと、すでに同内容が投稿済みのコメントはこの時点で除外され、除外理由が表示される。

この内容をユーザーに提示し、AskUserQuestion で承認を取る。PR ごとに投稿してよいか、`issue_policy` が `create` の PR については Issue を作ってよいかを確認する。ユーザーの承認なしに Step 3 へ進まない。

投稿するインラインコメントが 0 件の PR は、修正すべき指摘なし = Approve 相当として扱い、レビューイベントを `COMMENT` ではなく `APPROVE` で投稿する（1 件以上ある場合は `COMMENT`）。GitHub は comments 付きの `APPROVE` イベントを拒否するため両者は排他になる。dry-run 表示にもイベント名を出す。

### Step 3: 承認された分だけ投稿する

```bash
${CLAUDE_PLUGIN_ROOT}/skills/pr-adversarial-review/post.sh <RUN_DIR> --confirmed
${CLAUDE_PLUGIN_ROOT}/skills/pr-adversarial-review/post.sh <RUN_DIR> --pr 123 --confirmed
```

`--pr` を繰り返し指定すると、承認された PR だけに絞れる。`--issue-policy` を post.sh に渡す必要はない。collect.sh が各 PR の plan.json に書き込んだ値を post.sh が読む。

## 出力の構造

```
<RUN_DIR>/
├── tabs.txt              このランが作ったタブ ID。クリーンアップ対象
├── timing.jsonl           ロール別の実測時間(1行1レコード)
├── plans.json            全 PR の起案をまとめたもの
├── plan.md               人が読む要約
└── pr-<番号>/
    ├── reviewer-prompt.txt
    ├── findings.json     レビュワーの出力
    ├── refuter-prompt.txt
    ├── verdicts.json     反証者の出力
    ├── plan.json          投稿用に振り分けた結果
    └── *-tail.txt         ファイル出力に失敗したときのペイン末尾
```

`plan.json` の主なキー。

| キー | 内容 |
|---|---|
| `issue_policy` | この PR の out_of_scope の扱い(`create`\|`suggest`) |
| `confirmed` | 反証を通過した指摘 |
| `refuted` | 反証により棄却された指摘 |
| `unverified` | 反証者の判定が得られず保留された指摘。投稿しない |
| `inline_comments` | PR へ投稿するコメント。in-scope かつ行番号が有効なもの |
| `out_of_scope` | スコープ外の指摘。`issue_policy` に従って Follow Up Issue になるか、提案表示のみになる |

`timing.jsonl` の1行は `{role, agent, target, started_at, ended_at, duration_s, state}`。junct はレビュワーと反証者が同じ PR のタスクに合流するとフェーズを切り替えないため、この2ロールの内訳は junct からは取れない。ここが唯一の取得元になる。

## 設計上の決定と理由

レビュワーと反証者のモデル・effort・ツール権限は `skills/agent-routing` のロール定義(`review`、`refute`)を使う。両ロールとも読み取り専用のツール権限は同一で、モデルと effort が違う(`review` は sonnet high、`refute` は opus xhigh)。この対応をこのスキルの中に書かず `skills/agent-routing` の1箇所に集約している。ここに個別の許可リストを書くと、ロールを増やすたびに複数のスキルで同じリストを保守することになる。

レビュワーと反証者に読み取り専用の制約を明示している。`herdr agent start --kind claude` は新しい Claude Code を起動するため、グローバル CLAUDE.md の「レビューに対応したら Push する」を読み込む。複数 PR を同時にレビューさせると、同一チェックアウトで並行して編集と push が走りかねない。そこでプロンプト側で編集と git 操作と GitHub 書き込みを禁止し、`skills/agent-routing` の `readonly` ポリシーでもエージェント引数として `Edit` と `Bash(git:*)` と `Bash(jj:*)` を禁止している。情報取得は `gh pr view` と `gh pr diff` で行うため、チェックアウトを変更する必要がない。

成果の受け渡しをファイルにしている。Claude Code は代替スクリーンで動くため、画面から流れた行は herdr のスクロールバックに入らず、`agent read --lines` を増やしても回収できない。長いレビュー結果はペイン読み取りでは黙って切り詰められるため、各エージェントに JSON ファイルを書かせ、会話にはパスだけ返させている。

タブを 1 エージェント 1 タブにしている。同じタブで `pane split` を繰り返すと使いものにならない細さになるため、`tab create` の `.result.root_pane` を使う。指摘 1 件ごとに反証者を立てるとタブが爆発するので、反証は PR ごとに 1 人が指摘配列をまとめて検証する。

プロンプト投入後に working への遷移を確認している。`agent prompt` に `--wait` を付けずに投げてすぐ `agent wait` すると、まだ idle のままの相手を完了と誤認する。そのため投入後に状態が working になるまで待ってから join する。反証者は effort が高く初回応答が遅いため、`flow_agent_kick_role` が `skills/agent-routing` の `route_kick_ms` でロール別に待ち時間を延ばす。

`tab create` の直後にエージェントを起動しない。実測では tab 作成が返った時点でも zprofile が前景に残っており、`agent start` が要求する「シェルが前景にある空きペイン」の条件を満たさない。前景プロセスがシェル 1 つだけになるまで待ち、それでも失敗する場合は 3 回までリトライする。

このランが作ったタブ以外に触れない。タブ ID を `tabs.txt` に記録し、クリーンアップはそのファイルに書かれた ID だけを閉じる。`herdr tab list` に出てくる他の作業タブは対象にしない。

投稿前に行番号を差分で検証する。行番号がずれたインラインコメントはレビュイーに届かず、指摘全体をやり直すことになる。そこで `pulls/<n>/files` の patch から追加側と文脈行の行番号集合を作り、そこに載らないコメントを落とす。あわせて投稿直前に既存コメントを再取得し、同一箇所に同内容がある場合は投稿しない。

レビュー本文に suggestion ブロックを入れない。修正案はインラインコメント側にだけ含め、本文は「適正な実装」と「修正することが望ましいところ」の 2 節にする。out_of_scope の指摘は本文にもインラインコメントにも含めない。

`issue_policy` を collect 時に plan.json へ焼き込んでいる。post.sh に毎回 `--issue-policy` を渡させる設計にすると、collect 時の判断と post 時の指定がずれて事故になる。1回決めた方針を成果物に持たせ、post.sh はそれを読むだけにしている。

## 失敗したときの調べ方

`findings.json` が生成されない場合は `pr-<番号>/reviewer-tail.txt` にペインの末尾が保存される。エージェントが権限確認で止まっていた場合はここに現れる。`--keep-panes` を付けて再実行すればタブが残るので、`herdr agent read` や `herdr agent attach` で直接確認できる。

`verdicts.json` が得られなかった場合、全指摘は `unverified` として保留され投稿対象にならない。検証されていない指摘を投稿しないためで、これは意図した挙動になる。

### state=working のまま findings.json が得られない

`flow_agent_join` の `agent wait --until done --until blocked` が、レビュワーがまだ working のうちに返ることがある。実測では投入から 16 秒で返り、`FLOW_ARTIFACT_GRACE_MS` の既定 60 秒を待ってから「findings.json が得られなかった」で終わった。同じレビュワーをペインに残して観察すると、実際には 5 分 15 秒かけて 8KB の `findings.json` を書き終えた。`reviewer-tail.txt` は 0 バイトで、Claude Code が代替スクリーンで動くため手がかりにならない。

早く返る原因は未確定である。2 PR を並列で走らせたとき、`timing.jsonl` の 2 レコードが `started_at` も `ended_at` も秒単位で一致した。独立した 2 エージェントがそれぞれ一過性の blocked を拾ったのなら同じ秒に揃うのは不自然で、系統的な要因が疑われる。手動で `agent wait` を叩いた場合は timeout まで正しく待った（ただし投入直後のタイミングでは試していない）。`flow_agent_join` が `agent wait` を `|| true` で呼んで stderr を捨てているため、次に踏んだらそこの出口を記録すると切り分けられる。

`FLOW_ARTIFACT_GRACE_MS` を実際のレビュー時間より長く取る。猶予ループは 1 秒ごとに artifact を見て、できた時点で抜けるため、長くしても待ち損はしない。

```bash
export FLOW_ARTIFACT_GRACE_MS=1500000
```

`state=working` で終わった場合はレビュワーが生きている可能性が高い。`--keep-panes` を付けて再実行し、`herdr agent list` の `agent_status` が `done` になるのと `findings.json` ができるのを並べて観察すると切り分けられる。

## 反証段だけを単体で回す場合

既存の `findings.json` に対して反証者だけを走らせたいことがある。メインのセッションが自分で見つけた指摘を、レビュワーを通さずに検証にかける場合である。このとき collect.sh が持っている前提を写す必要がある。実測で 3 回連続して起動に失敗した。

- `agent-routing/lib/routing.sh` を source する。`flow_agent_start_role` が内部で `route_args_into` を呼ぶため、これが無いと「route_args_into が見つからない」で落ちる
- `FLOW_RUN_ID` を明示的に export する。flow.sh を source しただけでは未定義で、エージェント名の組み立てで unbound variable になる
- `local a="$1" b="$dir/$a"` のように同一の `local` 文で直前の変数を参照しない。`set -u` の下では未定義として落ちる
