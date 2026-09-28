# usage-feedback

使った Skill と SubAgent の名前を記録し、`/rate-usage` で Good・Fine・Bad を付ける function hook。

```
/rate-usage

  skill: pr-adversarial-review（3 回） はどうでしたか？
  [ Good ] [ Fine ] [ Bad ] [ Skip ]
```

答えると、その名前の未評価の記録すべてに同じ評価が書かれる。

## 記録するもの

| 対象 | 拾うイベント | 記録する値 |
|---|---|---|
| Skill | `skill.prompt` | 名前、時刻、セッションID |
| SubAgent | `agent.spawn` | `subagentType`、Agent ツールの `description`、時刻、セッションID |

`skill.prompt` は `/name` で叩いたとき、Skill ツールで呼んだとき、SubAgent が `skills:` でプリロードしたときのすべてで発火する。同じ名前が何度も並ぶので、評価を聞くときは名前で束ねる。

保存先は plugin store で、キーは `use:<セッションID>:<時刻>-<連番>`。実体は `~/.claude/plugins/store/usage-feedback_skills-dir-<hash>.json` にあるので、集計だけなら jq でも読める。

## コマンド

| 使い方 | 動き |
|---|---|
| `/rate-usage` | このセッションで使った未評価のものを、新しい順に聞く |
| `/rate-usage all` | 他のセッションの分も含めて聞く |
| `/rate-usage stats` | 使用回数と Good・Fine・Bad の内訳を表で出す。何も聞かない |

選択肢以外を打つと、点は付けずにその文だけ `note` に残る。評価は `skip` になるので、次からは聞かれない。

## 設定

`settings.json` の `pluginConfigs["usage-feedback@skills-dir"].options` に書く。

| キー | 既定値 | 内容 |
|---|---|---|
| `keepDays` | 90 | 記録を残す日数。過ぎたものは評価の有無にかかわらずセッション開始時に消す |

## 実装で踏んだ罠

- `agent.spawn` のフックは `next` を呼ばずに返すと SubAgent が起動しない。記録は必ず `next` の前に済ませ、失敗しても握りつぶす。`next` のあとで投げると `.catch` がもう一度 `next` を呼び、二重に起動する余地が残る
- `$.ui.ask` はダイアログを閉じられると reject する。1問ごとに評価を書いてから次を聞くので、途中で閉じても、そこまでの評価は残る。もう一度 `/rate-usage` を叩けば続きから聞く
- `$.store.set` はキー単位の read-modify-write で、同じファイルを複数セッションが触っても互いのキーを消さない。1ファイルを丸ごと書く方式にすると並行セッションで記録が飛ぶ
- `$.command.register` は built-in と同じ名前を拒否する。`/feedback` は built-in にあるので登録できない。拒否されたときは記録だけ溜まって評価できなくなるため、失敗を `$.ui.log` でその場に出す
- コマンドの登録は `session.start` で `await` する。ここで待たないと、最初のターンでコマンド一覧に出ない

## テスト

```bash
claude plugin test ~/.claude/skills/usage-feedback
bunx tsc --noEmit
```
