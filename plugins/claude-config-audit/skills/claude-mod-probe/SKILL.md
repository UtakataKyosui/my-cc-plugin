---
name: claude-mod-probe
description: Claude Code の engine が実際に何を渡してくるかを、使い捨ての function hooks プラグインで観測する。prompt.attachment / prompt.section / classic.* のフィールド、Skill 一覧や SubAgent 一覧の出どころ、watchPaths のファイル監視を確かめたいときに使う。Mod を書いていて型定義だけでは形が確定しないとき、claude plugin test では届かないイベントを検証したいときに読む。
---

# Claude Mod の挙動を観測する

型定義は engine の契約だが、どのイベントに何が載るかまでは書かれていない。
セクション名は列挙されておらず、Skill 一覧の出どころも書かれていない。
実物を見るには、使い捨てのプラグインを `--plugin-dir` で読ませて走らせる。

## 使い方

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/claude-mod-probe/lib/probe.sh

dir=$(probe_init attach)
out=/tmp/attachments.txt
probe_module "$dir" ${CLAUDE_PLUGIN_ROOT}/skills/claude-mod-probe/probes/attachments.ts "$out"
probe_run "$dir" "$out"
```

手動実行時は `${CLAUDE_PLUGIN_ROOT}` を `~/.claude/plugins/installed_plugins.json` の
`installPath` に置き換える。

ファイル監視のように、セッションが生きている間でないと起きない事象は
`probe_run_while` を使う。

```bash
dir=$(probe_init classic)
out=/tmp/classic.txt
probe_module "$dir" ${CLAUDE_PLUGIN_ROOT}/skills/claude-mod-probe/probes/classic.ts "$out"
probe_run_while "$dir" "$out" 8 sh -c "echo v2 >> $out.watched"
```

## 関数

| 関数 | 役割 |
|---|---|
| `probe_init <name>` | 使い捨てプラグインの骨組みを作り、ディレクトリを返す |
| `probe_module <dir> <probe.ts> <out>` | 観測モジュールを置き、`claude plugin validate` まで通す |
| `probe_run <dir> <out> [prompt]` | 短いセッションを1回走らせて結果を表示する |
| `probe_run_while <dir> <out> <秒> <cmd...>` | セッションを走らせたまま cmd を実行する |
| `probe_clean` | 作った使い捨てプラグインを消す |

## 同梱の観測モジュール

| モジュール | 見えるもの |
|---|---|
| `probes/attachments.ts` | 最初のユーザーメッセージに載る attachment の type と中身 |
| `probes/sections.ts` | システムプロンプトのセクション名と文字数 |
| `probes/classic.ts` | `classic.SessionStart` のキー、`classic.UserPromptSubmit` の `session_id` / `prompt_id`、`watchPaths` のファイル監視 |

## 実測で判明した罠

**`$.ui.log` は `-p` の出力に現れない。** `--output-format stream-json --verbose`
を付けても `ui_log` は出ない。観測結果は必ず `$.fs.write` でファイルへ出す。
プラグイン自体はロードされているので、ロード失敗と混同しやすい。

**`claude plugin test` では `classic.*` を検証できない。** テストハーネスは
engine 自身のステップを持たない。`prompt.submit` を誰かが `next` なしで
答えた時点で `classic.UserPromptSubmit` まで降りない。classic の形を
確かめたいときは実セッションで観測する。

**`claude plugin test` では `$` の noun を明示的に生やす必要がある。**
`mock.env(on, {...})` / `mock.store(on)` / `mock.clock(on)` を呼ばないと
「no implementation for env.get」でフックがスキップされる。エラーは出るので
気づけるが、フックが「何もしなかった」ように見える。

**Skill 一覧は `prompt.section` ではなく `prompt.attachment` にある。**
`type: "skill_listing"`。SubAgent 一覧は `type: "agent_listing_delta"`。
`prompt.section` が持つのは `memory` や `env_info_simple` など、engine 自身の
システムプロンプトの断片だけ。

**`watchPaths` は `-p` の短いセッションでは確かめられない。** headless は
即座に終わるため、監視対象を touch する隙がない。`probe_run_while` で
Bash の `sleep` を挟んで時間を作る。

**`$` はモジュール境界を越えられない。** `claude plugin validate` が静的に
追うため、観測モジュールも `$` を使う処理は同じファイルのトップレベル関数に
置く。import 先の関数へ `$` を渡すと validate が落ちる。

## 依存

- `claude` CLI（`claude plugin validate`、`claude -p --plugin-dir`）
- `python3`（待ち合わせ。`sleep` を使わないのは壁時計時間の浪費を避けるため）
