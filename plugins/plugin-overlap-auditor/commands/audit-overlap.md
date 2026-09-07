---
name: audit-overlap
description: >
  Skill/SubAgent/Command の役割重複を検出し、クラスタごとに keep/drop/coexist を推奨する。
  オプションで GitHub Issue を起票する。
argument-hint: "[--scope=all|repo|user-global|marketplace|builtin] [--dry-run|--post-issues] [--limit=N]"
allowed-tools:
  - Bash
  - Read
  - Agent
  - AskUserQuestion
---

# audit-overlap

Skill/SubAgent/Command の役割重複を監査し、整理の方針を GitHub Issue として記録します。

## フェーズ 0: 引数を解析する

`$ARGUMENTS` を確認する:
- `--scope=<scopes>`: 監査スコープ（デフォルト: `all`）
  - `repo` C2Lab plugins/
  - `user-global` `~/.claude/`
  - `marketplace` 外部マーケットプレイス由来
  - `builtin` Claude Code 組み込みコマンド
  - `all` すべて
- `--dry-run`: Issue を起票せず、ドラフト本文を表示する（デフォルト動作）
- `--post-issues`: 実際に GitHub Issue を起票する
- `--limit=N`: 起票する Issue の上限（デフォルト: 20）

引数が指定されていない場合、デフォルトで `--scope=all --dry-run` として動作する。

## フェーズ 1: 静的解析（アセット抽出 + クラスタリング）

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/audit_overlap.py" \
  --scope <scope> \
  --summary \
  --output /tmp/overlap-clusters.json
```

出力サマリを表示してユーザーに「N クラスタ検出」と報告する。

## フェーズ 2: LLM 分類（overlap-classifier Agent）

クラスタ JSON をエージェントに渡して keep/drop/coexist 判定を行う:

`overlap-classifier` エージェントを呼び出し、`/tmp/overlap-clusters.json` の内容を渡す。

エージェントの出力（`classified_clusters` JSON）を `/tmp/overlap-classified.json` に保存する。

## フェーズ 3: 結果プレビュー

分類結果を以下の形式でユーザーに表示する:

```
=== 役割重複クラスタ N 件 ===

[pr-review-001] PR レビュー系 (3件)
  ✂ drop推奨 : plugins/rust/agents/code-reviewer.md
  ✓ keep推奨 : plugins/code-review/agents/code-reviewer.md
  理由: 同名 agent、description 類似 (Jaccard 0.55)。汎用側を残す。

[vcs-001] jj/VCS 系 (4件)
  ✂ drop推奨 : plugins/harness-toolkit/skills/vcs-jj/ (marketplace の jj-vcs-workflow と重複)
  ✓ keep推奨 : plugins/jj-vcs-workflow/skills/jj-vcs-workflow/
  理由: 両者ほぼ同一スコープ。jj-vcs-workflow が詳細。

[pr-review-002] PR レビュー × Builtin 衝突 (2件)
  ⚡ builtin競合 : plugins/code-review/commands/code-review/ → 組み込み /review と同役割
  推奨: プラグイン側を削除し、組み込み /review を使う

...（最大 20 件まで表示）
```

`--dry-run` の場合はここで終了し、各クラスタの Issue ドラフト本文を折りたたみ表示する。

## フェーズ 4: 起票確認（`--post-issues` 時のみ）

`AskUserQuestion` で確認する:

- **question**: 「N 件のクラスタに対して GitHub Issue を起票してよいですか？」
  - options: 「起票する」「キャンセル（ドラフト保存のみ）」

## フェーズ 5: Issue 起票または終了

**起票する** を選択した場合:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/post_overlap_issues.py" \
  /tmp/overlap-classified.json \
  --limit <limit>
```

起票済み Issue URL をユーザーに提示する。

**キャンセル** の場合はドラフトが `~/.cache/overlap-audit/body-*.md` に保存されていることを案内する。

## 注意事項

- `gh` CLI がログイン済みであることが前提。未ログインの場合は `gh auth login` を案内する。
- `--post-issues` を省略した場合は **必ず dry-run** として動作し、Issue は起票されない。
- 1 回の実行で起票する Issue は `--limit` で制限する（デフォルト 20 件）。
- builtin との衝突は「参照情報」であり、削除の最終判断は人間が行う。
