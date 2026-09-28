---
name: herdr-issue-impl
description: GitHub Issue ごとに git worktree を切り、herdr のペインで実装エージェント（既定は Sonnet / effort high）を起動して PR 作成までを任せるスクリプト。複数 Issue の実装を herdr で並列に振り分けるとき、依存のある Issue を stacked PR で波ごとに流すときに使う。
allowed-tools: Bash(herdr *)
---

# herdr-issue-impl

手動実行時は `${CLAUDE_PLUGIN_ROOT}` が未設定なので、`claude plugin list` で確認するか `~/.claude/plugins/cache/my-cc-plugin/herdr-orchestration/<version>/` に置き換えて実行する。

`skills/herdr-fanout/lib/flow.sh` の上に、Issue 実装用の手順だけを載せた薄いスクリプトである。

## ファイル

| ファイル | 役割 |
|---|---|
| `run.sh` | spec を読み、Issue ごとに worktree 作成、ペイン起動、プロンプト投入、完了待ちをする |
| `prompt.tmpl` | 実装エージェントへの指示。`{{ISSUE}}` `{{BRANCH}}` `{{BASE}}` `{{WORKTREE}}` `{{DIR}}` `{{REPO}}` を置換する |

## 呼び出し

```bash
cat > ~/.cache/herdr-issue-impl/wave1/spec.txt <<'EOF'
3|feat/3-foo|main
4|feat/4-bar|feat/3-foo|/path/to/extra-note.md
EOF
ISSUE_IMPL_CARGO_TARGET_DIR=$REPO/target \
  ${CLAUDE_PLUGIN_ROOT}/skills/herdr-issue-impl/run.sh "$REPO" owner/repo \
  ~/.cache/herdr-issue-impl/wave1/spec.txt ~/.cache/herdr-issue-impl/wave1
```

spec の 1 行は `issue|branch|base|extra_prompt_file` で、4 列目は省略できる。base に前の Issue のブランチを書けば stacked PR になる。base は origin に push 済みである必要がある。

進捗は `<run_dir>/status.log` に `開始` `QUESTION` `BLOCKED` `DONE` の行で出る。Monitor で `tail -F` して拾う。

## 環境変数

| 変数 | 既定 | 意味 |
|---|---|---|
| `ISSUE_IMPL_MODEL` / `ISSUE_IMPL_EFFORT` | `sonnet` / `high` | 実装エージェントのモデルと effort |
| `ISSUE_IMPL_PARALLEL` | `3` | 同時に走らせる Issue 数 |
| `ISSUE_IMPL_TIMEOUT_MS` | `10800000` | 1 回の join の上限 |
| `ISSUE_IMPL_WT_ROOT` | `<repo>-wt` | worktree の置き場所。`<root>/issue-<n>` に作る |
| `ISSUE_IMPL_CARGO_TARGET_DIR` | 空 | 各ペインに渡す `CARGO_TARGET_DIR` |
| `ISSUE_IMPL_TEMPLATE` | `prompt.tmpl` | プロンプトの差し替え |

## 質問が来たとき

status.log に `QUESTION <dir>/question.json` が出たら、親セッションが利用者に聞いて答える。

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/herdr-fanout/lib/flow.sh
flow_agent_answer impl-<issue>-<run_id> <dir> "回答"
```

`question.json` が消えると run.sh は待ちを抜けて join に戻る。

## 罠と設計の理由

- ツール権限は `agent-routing` の `write` ポリシーを使わず、`--permission-mode auto` にしている。`write` ポリシーは `Bash(git:*)` と `Bash(cargo:*)` を許可していないため、commit と cargo check で `blocked` のまま止まる
- worktree は信頼済みのディレクトリの下に置く。新しいディレクトリを cwd にすると Claude Code が信頼の確認を出して止まるが、親ディレクトリが信頼済みなら出ない
- Rust のリポジトリで worktree ごとに target を持つと 1 本あたり数 GB を食う。`ISSUE_IMPL_CARGO_TARGET_DIR` で共有すると、cargo のロックで直列になる代わりに依存のビルドを使い回せる
- 親の Bash ツールで `gh pr create` を含む heredoc を書くと、PreToolUse の `check-pr-closes-issue.sh` がコマンド文字列に反応して止める。テンプレートは Write で書く
- worktree はスクリプトが消さない。PR の merge 後に親が `git worktree remove <root>/issue-<n>` で消す
