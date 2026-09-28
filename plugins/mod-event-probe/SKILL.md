---
name: mod-event-probe
description: Claude Code の function hook（Mod）で、どのイベントがどの値で発火するかをヘッドレス実行で記録して確かめる。Mod を書く前に、型定義に書かれていない発火条件（Workflow の agent() で agent.spawn が出るか、stream-json 起動で発火するか、$.http.fetch と $.env.get が使えるか等）を実測したいときに使う。
---

# mod-event-probe

イベントを記録するだけのプラグインを読み込み、`claude -p` をヘッドレスで走らせて `/tmp/mod-event-probe.jsonl` に書き出す。記録するのは `session.start`・`agent.spawn`・`skill.prompt`・`tool.call`（Skill と Agent）・`turn.step` である。記録するイベントを増やすときは `hooks/register.ts` に `on(...)` を足す。

| ファイル | 役割 |
|---|---|
| `hooks/register.ts` | イベントを JSON Lines で書き出すフック。`turn.step` では `$.agent.list()` に載っているか（`listed`）も記録する。env の `MOD_PROBE_SINK` があれば同じ内容をその URL へ POST し、`session.start` では `MOD_PROBE_TASK_ID` を読む |
| `skills/probe-skill/SKILL.md` | Skill 呼び出しの確認用の空の Skill（`mod-event-probe:probe-skill`） |
| `run.sh` | プロンプトを引数で渡す通常の `-p` で実行し、記録を表示する |
| `run-stream.sh` | vibe-kanban 系の executor と同じ stream-json 入出力で実行する。`sink.py` を立てて POST の到達と env の受け渡しも確かめる |
| `sink.py` | POST 本文を `/tmp/mod-event-probe-sink.jsonl` に追記する受け口 |

```bash
${CLAUDE_PLUGIN_ROOT}/run.sh "use a workflow: run one agent that returns hello" --plugin-dir ~/Documents/agent-router
${CLAUDE_PLUGIN_ROOT}/run-stream.sh "Invoke the Skill tool with skill mod-event-probe:probe-skill, then answer 'done'." --model sonnet --effort low
```

run-stream.sh の stdout と stderr は `/tmp/mod-event-probe-stdout.jsonl` と `/tmp/mod-event-probe-stderr.log` に残る。Skill が実際に呼ばれたかは stdout を `"name":"Skill"` で grep して確かめる。

## 実測で分かったこと（2026-09-24、Claude Code 2.1.281 の function hook early access）

- Workflow の `agent()` では `agent.spawn` が発火しない。`turn.step` は `agentId` 付きで来るが、その id は `$.agent.list()` に載らない
- `tool.call` の Workflow では引数が `e.script` のようにトップレベルに並ぶ（`e.input` ではない）。`script` を書き換えて `next` に渡すと、書き換えたスクリプトが実行・永続化される
- Workflow スクリプト内の `agent` と `phase` は再代入できる
- `turn.step` の `effort` は haiku では省かれる
- `$.session.messages()` はサブエージェントのループ内でも本会話を返す。サブエージェントの依頼文は `turn.step` からは読めない
- `-p --input-format=stream-json --output-format=stream-json` の起動でも `session.start`・`turn.step`・`agent.spawn`・`tool.call` は発火する
- `turn.step` の `model` は解決後の完全な ID（`--model sonnet` なら `claude-sonnet-5`）。`effort` は `--effort` の値がサブエージェントにも引き継がれる
- `$.env.get` は起動時に渡した env を読める。`$.http.fetch` で `http://127.0.0.1` への POST が届く
- `skill.prompt` は発火しない。Skill ツールで呼んだプラグインの Skill、プロジェクトの Skill のどちらでも、通常の `-p` と stream-json のどちらでも同じ。型定義（agent-router 0.2.0 同梱の `claude-code.d.ts`）は発火すると書いているが、実際と食い違う
- Skill の呼び出しは `tool.call` の `e.tool === "Skill"` で拾える。引数は `e.skill` にトップレベルで並び、サブエージェント内の呼び出しには `e.agentId` が付く。Agent も `e.tool === "Agent"` と `e.subagent_type` で拾える

## 罠

- macOS には `timeout` コマンドが無い
- `claude -p` は stdin を 3 秒待つ。`< /dev/null` を付ける
- `--setting-sources project` でユーザー階層のフックとプラグインを外す。外さないと導入済みの Mod と二重に動く。プロジェクト階層の Skill を試すときは `/tmp/.claude/skills/<name>/SKILL.md` に置く（実行時の cwd が `/tmp` のため）
- テストキット（`claude plugin test`）では `new Function` などの文字列からのコード生成が禁止される。生成したスクリプトの挙動はこのプローブで確かめる
- フック内で例外が出るとイベントは黙って素通りする。記録用のオブジェクトを組み立てる式（`e.text.length` など）で落ちると記録自体が残らないため、発火しないのか落ちたのか区別できない。未確認のフィールドは `typeof` や `Object.keys(e)` で記録する
- `$.env.get` の引数は文字列リテラルでなければならない。変数名を組み立てて読むことはできない

## 前提

- `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` で動く Claude Code
- `run-stream.sh` は `python3` を使う
