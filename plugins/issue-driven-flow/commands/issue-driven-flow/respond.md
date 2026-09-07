---
name: issue-driven-flow-respond
description: PR レビューの未返信スレッドを自律的に分類・修正・返信投稿する。--dry-run で実行予定をプレビュー可能。
argument-hint: "<PR URL or number> [--dry-run]"
allowed-tools:
  - Bash
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Task
  - Skill
  - AskUserQuestion
---

# /issue-driven-flow:respond

PR の未返信レビュースレッドを自動処理する。

未返信スレッドの抽出 → 3 分類 → valid-fix の修正実装 → jj safe-push → 返信投稿 を一気通貫で実行する。

## 引数

- `$ARGUMENTS`: PR の URL または PR 番号、オプションで `--dry-run`

例:
- `/issue-driven-flow:respond 123`
- `/issue-driven-flow:respond https://github.com/owner/repo/pull/123 --dry-run`

引数が未指定の場合は AskUserQuestion でユーザーに入力を求める。

**バリデーション**: PR URL は `https://github.com/` で始まること、番号は数字のみ。

`--dry-run` フラグを検出したら `DRY_RUN=true` として以降の手順で参照する。

## 実行手順

### Step 1: VCS 検出

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/vcs.py
```

出力の `vcs_type` を記録（`jj` or `git`）。

### Step 2: 未返信スレッド抽出

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_unanswered.py "$ARGUMENTS"
```

出力を `/tmp/pr-unanswered-<PR番号>.json` に保存。

`unanswered_threads` が空の場合は「未返信スレッドなし」として正常終了。

### Step 3: triage 入力構築

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/triage_input_builder.py < /tmp/pr-unanswered-<PR番号>.json > /tmp/pr-triage-input-<PR番号>.json
```

### Step 4: pr-triage SubAgent で分類

Task ツールで `pr-triage` SubAgent を起動する。

SubAgent への指示:
```
以下の PR レビュースレッドを分類してください。
入力データ: /tmp/pr-triage-input-<PR番号>.json を Read して使用する。
出力先: /tmp/pr-triage-<PR番号>.json

分類基準: valid-fix / invalid-reject / needs-human
```

### Step 5: dry-run 分岐

**DRY_RUN=true の場合**:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dry_run_report.py \
  --triage-file /tmp/pr-triage-<PR番号>.json \
  --pr <PR番号>
```
実行予定を PR にコメント投稿して終了。

**DRY_RUN=false の場合**: Step 6 へ。

### Step 6: 分類結果の確認

triage 結果をユーザーに表示して AskUserQuestion で確認:

```
valid-fix (N件): 自動修正 + 返信
invalid-reject (N件): 返信のみ（却下）
needs-human (N件): スキップ

[はい、実行する] [いいえ、キャンセル]
```

### Step 7: valid-fix の修正実装

Task ツールで `review-fixer` SubAgent を起動。修正完了後 `/tmp/review-fix-plan-<PR番号>.json` を生成させる。

### Step 8: 検証

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/verifier.py
```

失敗時は最大 3 回 Step 7 に戻って再修正。3 回失敗はユーザーに報告して中断。

### Step 9: コミット

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/committer.py /tmp/review-fix-plan-<PR番号>.json
```

コミットメッセージは Conventional Commits 形式 + Issue 番号を維持する。

### Step 10: Push

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/push.py
```

jj の場合、jj-exec-aliases 導入時は `jj safe-push` コマンド（alias）を使用し、未導入時は `jj git push` を使用。git の場合は `AskUserQuestion` で確認後 push。

### Step 11: 返信投稿

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/post_reply.py \
  --reply-file /tmp/pr-triage-<PR番号>.json \
  --repo <owner/repo>
```

必ず `gh api -X POST .../comments` + `in_reply_to` を使用。`gh pr comment` は使用しない。

### Step 12: 完了報告

処理スレッド数・コミット数・push 状態・返信数のサマリを表示。
needs-human スレッド一覧を提示して手動対応を促す。

マージ準備完了の場合: `/issue-driven-flow:finish-feature` で後始末できることを案内する。
