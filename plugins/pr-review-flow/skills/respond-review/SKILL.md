---
name: respond-review
description: PR レビューコメントへの対応を end-to-end で実行する。コード修正 → linter/formatter → テスト → commit & push → GitHub 返信 → セッションサマリーをアトミックに処理する。
when_to_use: 「レビューに対応して」「PR のコメントに返信して」「review を resolve して」と指示されたとき。レビューコメントへの対応を一括で終わらせたいとき。
argument-hint: "[pr-number]"
allowed-tools: Bash(gh wheel *) Bash(gh api *) Bash(gh pr view *) Bash(gh pr diff *) Bash(jj log *) Bash(jj status *) Bash(jj diff *) Bash(jj bookmark list *) Bash(jj commit *) Bash(jj safe-push *) Bash(pnpm *) Bash(mise exec *) Bash(ruff *)
---

# Respond to PR Review Comments

引数: PR 番号または URL（例: `/respond-review 123`）

## Step 1: PR の未解決コメントを取得する

```bash
gh wheel review threads <PR番号>
```

未解決スレッドの一覧を読み込む。`gh wheel` が使えない場合は以下で取得:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/reviews
gh api repos/{owner}/{repo}/pulls/{pr}/comments
```

未解決コメントを番号付きでリストアップしてから作業を開始する。

## Step 2: コード修正

各コメントに対して最小限の修正を加える。

- 修正後は対応する linter / formatter を実行する（TypeScript: `pnpm exec prettier --write`、Python: `ruff format`）
- テストが存在する場合は `mise exec -- pnpm turbo test --filter=<package>` を実行する
- 修正は ExitPlanMode なしに直接実装する（計画フェーズを設けない）

## Step 3: コミット & Push

```bash
jj commit -m "fix(<scope>): レビュー指摘に対応する (#<issue番号>)"
jj safe-push
```

Issue 番号は接尾辞に置く。issue-driven-flow の commit-msg フックが `<type>(<scope>): <subject> (#NNN)` 形式を強制しているため、接頭辞に置くと弾かれる。push は `jj safe-push` alias を使う。

## Step 4: GitHub へ返信（重複防止つき）

各スレッドへ返信する前に、必ず最新状態を再取得して重複をチェックする:

```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments
```

同じスレッドに org メンバーからの返信がすでにある場合はスキップする。

返信投稿のエンドポイント（**PR番号を必ず含める**）:

```
POST /repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies
```

```bash
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies \
  -X POST -f body="対応内容の説明"
```

- `{pr_number}` を省略したエンドポイントは誤り（422 エラーになる）
- 全スレッドに返信したか確認してから次ステップへ進む

## Step 5: セッションサマリーを書く

`session-summaries/${CLAUDE_CODE_SESSION_ID}.md` を作成・更新する。書式は `~/.claude/rules/session-summary.md` を参照する（未設定の環境ではこのステップを省略してよい）:

```markdown
## <日付>

### 作業内容
- PR #<番号>: <タイトル>

### 対応したコメント
1. <コメント概要> → <対応内容>
2. ...

### 変更ファイル
- <ファイルパス>

### ステータス
- Push: 完了
- GitHub 返信: 全スレッド完了（<N>件）
- CI: 実行中 / 通過

### 未解決事項
- （なければ「なし」）
```

このステップを省略しない。リマインダーを待たずに書く。
