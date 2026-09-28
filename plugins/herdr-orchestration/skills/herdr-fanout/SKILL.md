---
name: herdr-fanout
description: herdr のペイン上に複数のコーディングエージェントを並列展開し、プロンプト投入と完了待ちと結果回収を行うシェル関数ライブラリ。Dynamic Workflow の phase / parallel / pipeline に相当するプリミティブを bash で提供する。複数エージェントに並列で作業させるスクリプトを書くとき、herdr でファンアウトするとき、他のスキルからエージェント並列実行の土台として使うときに読む。
allowed-tools: Bash(herdr *)
---

# herdr-fanout

手動実行時は `${CLAUDE_PLUGIN_ROOT}` が未設定なので、`claude plugin list` で確認するか `~/.claude/plugins/cache/my-cc-plugin/herdr-orchestration/<version>/` に置き換えて実行する。

`lib/flow.sh` を source すると、herdr の CLI の上に Dynamic Workflow と同じ構造を組める。ファンアウトするスクリプトを書くたびに同じ罠を踏み直さないための土台にする。

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/herdr-fanout/lib/flow.sh
```

このライブラリを使う側は `set -euo pipefail` を前提にしてよい。

## 関数

| 関数 | 役割 |
|---|---|
| `flow_init` | 依存コマンドと `HERDR_ENV` を検証し、実行 ID `FLOW_RUN_ID` を決める |
| `phase <title>` | 段階の区切りを stderr に出す |
| `log <msg>` | 進捗を stderr に出す |
| `flow_spawn <label> <cwd> [--env KEY=VALUE]...` | タブを作り、使える状態になったルートペイン ID を stdout に返す。`--env` はそのペインだけに環境変数を注入する |
| `flow_wait_shell_ready <pane> [timeout_ms]` | ペインの前景がシェル 1 つだけになるまで待つ |
| `flow_workspace_create <label>` | 専用のワークスペースを `--no-focus` で作り、以降の `flow_spawn` の作成先にする |
| `flow_agent_ask_instructions <dir>` | ペイン側へ渡す質問の書き方を出力する |
| `flow_agent_question <dir>` | 未回答の質問があれば中身を返す |
| `flow_agent_answer <name> <dir> <text>` | 回答を書いてペイン側を再開させる |
| `flow_agent_start <name> <kind> <pane> [-- args...]` | エージェントを起動する。失敗時は 3 回まで再試行する |
| `flow_agent_start_role <name> <role> <pane> [kind=claude]` | `skills/agent-routing` のロール定義でモデル・effort・ツール権限を組み立てて起動する |
| `flow_agent_kick <name> <prompt_file>` | プロンプトを投入し、実際に届いたことを確認する。届かなければ再送する |
| `flow_agent_kick_role <name> <prompt_file> <role>` | ロール別の待ち時間(`route_kick_ms`)で投入する。effort の高いロールは初回応答が遅く、既定の待ち時間だとプロンプトが黙って捨てられることがある |
| `flow_agent_join <name> [timeout_ms] [artifact]` | done か blocked になるまで待ち、最終状態を stdout に返す。artifact を渡すと成果物が現れるまで `FLOW_ARTIFACT_GRACE_MS`(既定 60000)だけ追加で待つ |
| `flow_agent_status <name>` | 現在の状態を stdout に返す |
| `flow_record_timing <timing_file> <role> <name> <target> <start_ts> <end_ts> <state>` | ロール別の実測時間を1行の JSON として追記する |
| `flow_cleanup` | このランが作ったタブだけを閉じる |

`flow_agent_start_role` と `flow_agent_kick_role` を使う場合は、`skills/agent-routing/lib/routing.sh` を先に source しておく。関数の中で source し直さない。`( ) &` のサブシェルで並列に走るスクリプトでは、都度読み直すと無駄になる。

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/herdr-fanout/lib/flow.sh
source ${CLAUDE_PLUGIN_ROOT}/skills/agent-routing/lib/routing.sh
flow_init

flow_agent_start_role "$name" refute "$pane"
flow_agent_kick_role "$name" "$dir/prompt.txt" refute
```

## 使い方の型

```bash
#!/usr/bin/env bash
set -euo pipefail
source ${CLAUDE_PLUGIN_ROOT}/skills/herdr-fanout/lib/flow.sh
flow_init

RUN_DIR="$HOME/.cache/my-flow/$FLOW_RUN_ID"
mkdir -p "$RUN_DIR"
export FLOW_TAB_LOG="$RUN_DIR/tabs.txt"; : >"$FLOW_TAB_LOG"
trap flow_cleanup EXIT

run_one() {
  local item="$1" dir="$RUN_DIR/$item"
  mkdir -p "$dir"
  local pane name
  pane=$(flow_spawn "work $item" "$PWD")
  name="job-$item-$FLOW_RUN_ID"
  flow_agent_start "$name" claude "$pane" -- --allowed-tools Read Write "Bash(gh:*)"
  printf '結果を %s/out.json に Write で書き、最後はパスだけ返してください。\n' "$dir" >"$dir/prompt.txt"
  flow_agent_kick "$name" "$dir/prompt.txt"
  flow_agent_join "$name" 1800000
  [ -s "$dir/out.json" ] || { log "$item: 結果ファイルが得られなかった"; return 1; }
}

phase "fan out"
pids=()
for item in a b c; do
  while [ "$(jobs -rp | wc -l | tr -d ' ')" -ge 3 ]; do perl -e 'select(undef,undef,undef,1)'; done
  ( run_one "$item" ) &
  pids+=("$!")
done
for p in "${pids[@]}"; do wait "$p" || true; done
```

段階ごとに全員を待ち合わせる barrier ではなく、item ごとに独立したパイプラインをサブシェルで流す。これで item A の検証中に item B の一段目が走る。

## 環境変数

| 変数 | 既定 | 意味 |
|---|---|---|
| `FLOW_TAB_LOG` | 空 | 作成したタブ ID の記録先。設定しないとクリーンアップが働かない |
| `FLOW_KEEP_PANES` | `0` | `1` にすると終了後もタブを残す。デバッグ用 |
| `FLOW_AGENT_GRACE_MS` | `8000` | 起動後、最初の投入までの猶予 |
| `FLOW_KICK_WAIT_MS` | `20000` | 投入が届いたと判断するまでの待ち時間 |
| `FLOW_RUN_ID` | 自動生成 | 実行 ID。エージェント名に使うため英数字 12 文字まで |
| `FLOW_WORKSPACE` | 空 | タブの作成先ワークスペース。空なら呼び出し元の `$HERDR_WORKSPACE_ID` を使う |

## ペイン側からの質問を中継する

ペイン側のエージェントに AskUserQuestion を禁止したうえで、質問を親へ回す経路を用意している。ペインで選択 UI を出させてキーを送って答えさせる経路は、Claude Code が代替スクリーンで動くため読み取りが不安定になる。

```bash
flow_agent_start "$name" claude "$pane" -- \
  --allowed-tools Read Write --disallowed-tools AskUserQuestion
{ cat prompt-head.txt; flow_agent_ask_instructions "$dir"; } >"$dir/prompt.txt"
flow_agent_kick "$name" "$dir/prompt.txt"

while :; do
  flow_agent_join "$name" 300000 >/dev/null
  q=$(flow_agent_question "$dir")
  [ -n "$q" ] || break
  # ここで親が利用者に聞く。AskUserQuestion は親のセッションが呼ぶ
  flow_agent_answer "$name" "$dir" "$回答"
done
```

ポーリングを使わない。ペイン側は質問を書いた時点で応答を終えるため、herdr の状態遷移だけで進む。エージェントに `sleep` を許可する必要もない。

## ワークスペースを分けて走らせる

`flow_workspace_create` を呼ぶと、以降の `flow_spawn` はそのワークスペースへタブを作る。`--no-focus` で作るため画面は切り替わらず、利用者の作業タブとも混ざらない。`flow_cleanup` は自分が作ったワークスペースだけを閉じる。

## 実測で分かった罠

実際に herdr 上で動かして確認した挙動を記録する。ここに書いた対処はすべて `lib/flow.sh` に実装済みで、呼び出し側が意識する必要はない。

`agent start` はエージェントが入力を受け付ける前に返る。herdr がエージェントを検出した時点で成功が返るが、Claude Code の TUI はまだ起動中で、MCP サーバーが多い環境では数秒かかる。この間に送ったプロンプトはエラーにならず捨てられる。`agent prompt` は成功を返し、`interactive_ready` も true のまま、入力欄は空のままになる。そのため投入は届いたことを状態遷移で確認し、届かなければ再送する。実測では 2 回目で確実に届いた。

`tab create` が返った直後のペインはまだ使えない。zprofile の処理が前景に残っており、`agent start` は `agent_pane_busy` を返す。前景プロセスがシェル 1 つだけになるまで待ってから起動し、それでも失敗する場合は再試行する。

`tab create` に `--workspace` を渡さないと、UI でフォーカスされているワークスペースにタブが作られる。それは他クライアントが作業中の場所である可能性がある。必ず `$HERDR_WORKSPACE_ID` を渡す。

結果はペイン読み取りではなくファイルで受け取る。Claude Code は代替スクリーンで動くため、画面から流れた行は herdr のスクロールバックに入らない。`agent read --lines` を増やしても回収できず、長い出力は黙って切り詰められる。エージェントには成果物をファイルに書かせ、会話にはパスだけ返させる。

`agent prompt` に `--wait` を付けずに投げてすぐ `agent wait` すると、まだ idle の相手を完了と誤認する。`flow_agent_kick` が working への遷移を確認してから `flow_agent_join` に進む。

`agent wait` に `--until` を渡さないと idle も完了とみなす。これが最も高くついた罠である。`herdr agent wait --help` は「Without --until, matches idle, done, or blocked」と書いてあり、Claude Code はプロンプト投入の直後とツール呼び出しの合間に idle へ落ちる。実測した遷移は投入から 2 秒後に idle、4 秒後に working、8 秒後に done で、その後 done のまま定常になった。この最初の idle を拾って `agent wait` が即座に返るため、`flow_agent_kick` が working を確認していても意味を持たない。kick が working を見た次の瞬間にエージェントが一度 idle へ落ちれば、そこで join が抜ける。

実際に `pr-adversarial-review` でレビュワーが 4 分 21 秒かけて書いた `findings.json` を取りこぼし、成果物が存在するのに「得られなかった」と判定してその PR をスキップした。`flow_agent_join` は `--until done --until blocked` を渡す。`blocked` を残すのは、権限プロンプトで止まったエージェントをタイムアウトまで待たないためである。

`done` はファイルの書き込み完了より先に立つことがある。`flow_agent_join` の第3引数に成果物のパスを渡すと、状態が確定したあとも成果物が現れるまで `FLOW_ARTIFACT_GRACE_MS` だけ待つ。この 2 段構えにする。状態待ちを成果物のポーリングだけに置き換えると、指摘 0 件で成果物を書かないエージェントを毎回タイムアウトまで待つことになる。

作成したタブ ID は配列ではなくファイルに記録する。サブシェルで並列に spawn すると配列は親に伝わらない。またクリーンアップはこのファイルに書かれた ID だけを閉じる。`herdr tab list` に出てくる他の作業タブには触れない。

`flow_workspace_create` を command substitution で呼ばない。サブシェルになり `FLOW_WORKSPACE` の代入が親へ伝わらず、`flow_spawn` が呼び出し元のワークスペースへタブを作り続ける。ID が要るときは呼んだあとに `$FLOW_WORKSPACE` を読む。

ペイン側へ渡す制約の説明は、実際のツール権限と一致させる。`--disallowed-tools AskUserQuestion` を渡さずに「AskUserQuestion は使えません」と伝えたところ、ペイン側のエージェントが嘘の制約を課すプロンプトインジェクションだと判定し、手順全体を拒否した。ファイル経由で回答を受け取らせる形も、任意のパスの内容を信用させる指示に見えるため拒否の材料になる。`flow_agent_ask_instructions` の文面は、回答ファイルが新しい指示ではなく自分の質問への回答であることを明示している。

エージェントの cwd に新しい一時ディレクトリを渡さない。Claude Code がそのフォルダを信頼するかを尋ね、`blocked` のまま止まる。cwd は呼び出し元のままにして、成果物のパスを絶対パスで渡す。

## 子エージェントに渡す引数

子エージェントは新しい Claude Code として起動するため、グローバル CLAUDE.md をそのまま読み込む。読み取り専用で働かせたい場合は、プロンプトでの禁止と引数での禁止を両方かける。

```bash
--allowed-tools Read Write Grep Glob "Bash(gh:*)" \
--disallowed-tools Edit NotebookEdit "Bash(git:*)" "Bash(jj:*)" "Bash(herdr:*)"
```

許可リストに載っていないツールは実行時に確認を求めて止まる。止まった相手は `blocked` になるため、子エージェントに必要なツールは起動時にすべて許可しておく。

## このライブラリを使っているスキル

- `pr-adversarial-review` — 複数 PR の敵対的レビューを並列実行する。ロール別モデル振り分けは `skills/agent-routing` を参照する
