---
name: agent-routing
description: タスクの性質(実装・レビュー・敵対的検証など)をロールに変換し、そのロールに割り当てるモデル・effort・ツール権限・junct フェーズを1箇所から引き出すシェル関数ライブラリ。herdr のペイン起動と agents/*.md の軽量サブエージェントの両方がここを参照する。ロール別にモデルを振り分けたいとき、herdr-fanout の上に構築するときに使う。
---

# agent-routing

手動実行時は `${CLAUDE_PLUGIN_ROOT}` が未設定なので、`claude plugin list` で確認するか `~/.claude/plugins/cache/my-cc-plugin/herdr-orchestration/<version>/` に置き換えて実行する。

ロールと、そのロールに割り当てるモデル・effort・ツール権限・junct フェーズの対応を1箇所に定義する。この定義を `skills/herdr-fanout` のペイン起動と、`agents/role-*.md` の軽量サブエージェントの両方が参照する。定義が2箇所に実体化すると必ず食い違うため、値の出どころはここだけにする。

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/agent-routing/lib/routing.sh
```

## ロール表

`route_table` を実行すると現在の値が出る。このファイルには値を書かない。散文と実装の2箇所に同じ値を書くと必ず食い違うためである。

```bash
bash -c 'source ${CLAUDE_PLUGIN_ROOT}/skills/agent-routing/lib/routing.sh; route_table'
```

`status` が `confirmed` のロール(`implement` / `review` / `refute`)は今回のスコープで確定した割り当てである。`proposed` のロール(`fix` / `triage` / `design`)は将来の拡張を見込んだ候補であり、不要なら `data/roles.json` から削ってよい。

## 関数

| 関数 | 役割 |
|---|---|
| `route_model <role>` | モデル名を返す |
| `route_effort <role>` | effort を返す |
| `route_policy <role>` | ポリシー名(`readonly`\|`write`)を返す |
| `route_grace_ms <role>` / `route_kick_ms <role>` | ロールに応じた待ち時間(ms)を返す |
| `route_junct_phase <role>` | junct の開始関数名(`start_task` など)を返す |
| `route_args_into <配列名> <role>` | claude CLI の引数ベクタを呼び出し側の配列へ直接詰める |
| `route_frontmatter_tools <role>` | 軽量経路(`agents/role-*.md`)の `tools:` 値を返す。軽量経路を持たないロールに対してはエラーにする |
| `route_table` | ロール表・ポリシー表・軽量経路の対応をまとめて出力する |

## herdr のペイン経路から使う

`route_args_into` は stdout で値を返さず、nameref で呼び出し側の配列へ直接詰める。stdout 経由にすると呼び出し側が `read -r -a` で受け直すことになり、空白を含む引数が IFS 分割で壊れる。これは `pr-adversarial-review` の旧実装 (`RRAR_AGENT_ARGS`) が実際に持っていた制約で、置換方式だったために `--disallowed-tools` を上書きで丸ごと落とせた。ここでは追加方式にして、この経路を作らない。

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/herdr-fanout/lib/flow.sh
source ${CLAUDE_PLUGIN_ROOT}/skills/agent-routing/lib/routing.sh

local args=()
route_args_into args refute
flow_agent_start "$name" claude "$pane" -- "${args[@]}"
```

herdr-fanout 側は `flow_agent_start_role <name> <role> <pane>` としてこれをラップしている。詳細は `skills/herdr-fanout/SKILL.md` を参照する。

## 軽量経路(agents/role-*.md)から使う

ペインを開かずに Agent ツールで単発のサブエージェントを起動したい場合は、`agents/role-implementer.md` / `agents/role-reviewer.md` / `agents/role-verifier.md` の `model:` と `effort:` フロントマターを直接使う。単発タスクではこちらが軽い。

この経路のツール権限はペイン経路の `policy` 表とは形が違う。`claude --allowed-tools` は `Bash(gh:*)` のような細かいサブパターンを空白区切りで取れるが、`agents/*.md` の `tools:` はカンマ区切りのツール名一覧で、`Bash(...)` のサブパターンは表現できない。`route_frontmatter_tools` は `data/agent-tools.json` という別の対応表から値を返し、ペイン経路の `policy` の値は流用しない。`review` と `refute` はペイン経路では effort だけが違い読み取り専用ポリシーは同一だが、軽量経路では両方とも `Read, Grep, Glob, Bash` という同じ粒度の粗い許可になる。`Bash` 全体が使えるため、ペイン経路より分離が弱いことを承知して使う。

## 環境変数による上書き

| 変数 | 効果 |
|---|---|
| `AGENT_ROUTE_MODEL_<ROLE>` | 例: `AGENT_ROUTE_MODEL_REFUTE=haiku`。指定ロールのモデルだけを差し替える |
| `AGENT_ROUTE_EFFORT_<ROLE>` | 例: `AGENT_ROUTE_EFFORT_REVIEW=low`。指定ロールの effort だけを差し替える |
| `AGENT_ROUTE_EXTRA_ARGS` | `route_args_into` の末尾に追加する引数。**追加であり置換ではない** |
| `AGENT_ROUTING_DIR` | `data/` の場所を上書きする |
| `AGENT_ROUTING_ROLES` | `roles.json` の場所だけを上書きする |

`AGENT_ROUTING_ROLES` は `roles.json` を単独で差し替えたいときに使う。`~/.claude/hooks/run-design-review.sh` と別プラグイン `agent-router` はこのプラグインの外側から `roles.json` だけを参照する。このプラグインをインストールした環境でそれらから使う場合は、次のように `AGENT_ROUTING_LIB` と `AGENT_ROUTING_ROLES` を export してから `routing.sh` を source する。

```bash
export AGENT_ROUTING_LIB="$HOME/.claude/plugins/cache/my-cc-plugin/herdr-orchestration/<version>/skills/agent-routing/lib/routing.sh"
export AGENT_ROUTING_ROLES="$HOME/.claude/plugins/cache/my-cc-plugin/herdr-orchestration/<version>/skills/agent-routing/data/roles.json"
source "$AGENT_ROUTING_LIB"
```

`AGENT_ROUTE_EXTRA_ARGS` は素朴に空白分割して展開する。フラグとその値がそれぞれ別の argv 要素になる分には問題ないが、1つの引数の中に空白を含めたい場合(例: 独自のツール許可パターン)は、既存の慣習に合わせてコロン区切りの形(`Bash(foo:*)`)で書き、空白を持ち込まない。

既存の `RRAR_AGENT_ARGS` / `PRAR_AGENT_ARGS` は廃止した。両方とも配列を置換する方式で、モデルを足す目的で設定するとガードレールが丸ごと外れる作りだったため、後方互換を保たずここへ統合した。

## junct フェーズとの対応

| role | junct の開始関数 | 計測される区分 |
|---|---|---|
| `implement` | `start_task` | 実装 |
| `review` | `start_review_task` | レビュー実行 |
| `refute` | `start_review_task` | レビュー実行 |
| `fix` | `start_fix_task` | 修正対応 |
| `triage` / `design` | `start_other_task` | その他 |

同じ PR のレビュワーと検証者は同じ junct タスクに紐づくため、`review` と `refute` を両方 `start_review_task` に開始しても junct 側は既存セッションを継続するだけで、フェーズを切り替えない。junct からはレビュワーと検証者の内訳が分からない。この内訳が必要な場合は `skills/herdr-fanout` が書き出す `timing.jsonl` の実測時間を使う。詳細は Skill `junct-workflow:junct-estimate` を参照する。

## 罠

- `route_args_into` を関数の中で毎回 source し直さない。`herdr-fanout` を使うスクリプトは PR ごとに `( ) &` のサブシェルで並列に走ることが多く、その中で source すると読み直しになる。スクリプトの先頭で一度だけ source する。
- ロールを追加・変更したら `doctor.sh` を実行する。`data/roles.json` と `agents/role-*.md` のフロントマターが食い違っていないかを検査する。
- `route_frontmatter_tools` は軽量経路を持たないロール(`fix` / `triage` / `design`)に対してエラーで止まる。これは仕様である。これらのロールは今のところペイン経路専用にしている。
