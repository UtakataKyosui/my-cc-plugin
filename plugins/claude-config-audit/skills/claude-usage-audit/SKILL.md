---
name: claude-usage-audit
description: Claude Code のセッション transcript から Skill・SubAgent・Hook の起動実績を集計する。リポジトリ固有の Skill や Hook が実際に使われているかを棚卸ししたいとき、未使用の設定を削除する根拠を集めたいとき、フックが発火しているかを確認したいときに使う。
---

# Claude Code 使用実績の監査

`~/.claude/projects/**/*.jsonl` のセッション transcript を集計し、Skill・SubAgent・Hook の起動実績を出す。

## 使い方

```bash
PROJ=gajumaru-next        # ~/.claude/projects/ 配下のディレクトリ名に含まれる文字列
SINCE=2026-08-16

find ~/.claude/projects -path "*${PROJ}*" -name '*.jsonl' -newermt "$SINCE" > /tmp/files.txt
while read -r f; do
  jq -c --arg since "$SINCE" -f ${CLAUDE_PLUGIN_ROOT}/skills/claude-usage-audit/lib/extract.jq "$f" 2>/dev/null
  # 手動実行時は ${CLAUDE_PLUGIN_ROOT} を ~/.claude/plugins/installed_plugins.json の
  # installPath に置き換える
done < /tmp/files.txt > /tmp/rows.jsonl

jq -r 'select(.k=="skill")|.name' /tmp/rows.jsonl | sort | uniq -c | sort -rn
jq -r 'select(.k=="agent")|.name' /tmp/rows.jsonl | sort | uniq -c | sort -rn
jq -r 'select(.k=="hook")|[.ev,.cmd,.st]|@tsv' /tmp/rows.jsonl | sort | uniq -c | sort -rn
```

`extract.jq` は 1 レコードを `{k: "skill"|"agent"|"hook"|"cmd", ...}` に正規化する。`k=="cmd"` はスラッシュ起動（ユーザーメッセージの `<command-name>`）である。

## 実測で判明した罠

| 罠 | 内容 | 対処 |
|---|---|---|
| **記録は網羅的でない** | 登録済みで実際に動いているフックが transcript に残らないことがある（実測: UserPromptSubmit 728 機会に対し該当スクリプトの記録 1 件、フック自身のログには 355 件）。条件は特定できていない。stdout の有無で決まるという説明は、stdout 空で記録された成功レコードが 20 件ある事実と合わない | 発火件数は下限値として扱う。フックが独自にログを吐くなら（`.claude/ai-notes/*.jsonl` など）そちらと突き合わせる |
| **statusMessage が command を置き換える** | settings に `statusMessage` を書いたフックは `attachment.command` にスクリプトパスではなくその文字列が入る | settings 側の `statusMessage` を読んでラベル → スクリプトの対応表を作る。同名スクリプトがグローバルとリポジトリ両方にある場合、`statusMessage` の差が唯一の識別子になることがある |
| **`PreToolUse:Edit` の欠落は非発火の証拠にならない** | `PreToolUse:Bash` は大量に記録されるのに `PreToolUse:Edit` はほぼ残らない。理由は未解明 | ブロック実績（`hook_blocking_error`、または stdout 非空の `hook_success`）の有無だけを主張する |
| **jq のプリティ出力で件数を数え間違える** | `jq 'select(...)' \| wc -l` はオブジェクトが複数行に展開されて件数が膨らむ | 件数を数えるときは必ず `jq -c` を使う |
| **古い worktree のフックエラーが混ざる** | `.claude/hooks/` を持たない古いブランチの worktree で exit 127 が大量に出る。メインのチェックアウトでの実行実績と区別が要る | エラーレコードの `stderr` に含まれるパスで worktree を切り分ける |
| **登録状態の確認が先** | 未登録のフックは発火しえない。`settings.json`（committed）と `settings.local.json`（opt-in）の両方を見る | `jq -r '.hooks\|to_entries[]\|.value[]\|.hooks[]\|.command'` で両方から抽出して差分を取る |

## 依存

`jq`、`find`、GNU 互換でない `find -newermt`（macOS の BSD find でも動く）
