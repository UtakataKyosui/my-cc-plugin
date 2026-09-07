---
name: task-start
description: >
  Issue または PR への着手を宣言し、ブランチ作成・自己アサイン・着手ラベル付与まで一連のワークフローを実施する。
  以下の場合に使用:
  (1) 「Issue #N に着手して」「この Issue を始める」と指示されたとき
  (2) 「PR #N のレビューを始める」「レビュー対応を開始して」と指示されたとき
  (3) 「着手宣言」「作業開始」「start」というキーワードが含まれるとき
version: 1.0.0
---

# task-start スキル

Issue または PR への着手宣言から作業開始まで一貫して実施する。

## Issue に着手するフロー

### Step 1: Issue 内容の確認

```bash
rtk gh issue view <N>
```

要件・受け入れ条件・関連リンクを把握する。

### Step 2: 自己アサイン

```bash
rtk gh issue edit <N> --add-assignee @me
```

### Step 3: ブランチ作成

**git の場合:**
```bash
rtk git fetch origin main
rtk git checkout main && rtk git pull origin main
rtk git checkout -b feat/<N>-<slug>
```

**jj の場合:**
```bash
jj git fetch --remote origin
# jj-exec-aliases 導入時は jj safe-new、未導入時は jj new で次の Change へ移動
```

ブランチ名の規則: `<type>/<issue-number>-<short-slug>`
- `feat/123-add-user-profile`
- `fix/456-null-pointer-error`

### Step 4: 着手コメント（任意）

```bash
rtk gh issue comment <N> --body "着手しました。"
```

## PR レビューに着手するフロー（自分がレビュワー）

### Step 1: PR 概要確認

```bash
rtk gh pr view <N>
```

### Step 2: レビュー対応指示の取得（自分が author の場合）

```bash
rtk gh my-task prompt <N>
```

このコマンドは PR に届いたレビューコメントへの対応指示を Markdown で出力する。
出力された指示に従って `pr-workflow` プラグインを使ってレビュー対応を進める。

### Step 3: コードの確認（自分がレビュワーの場合）

```bash
rtk gh pr diff <N>
rtk gh pr checks <N>
```

レビューには `pr-workflow` プラグインの `pr-review-format` スキルを使う。

## 優先度の判断

着手前に `my-task` スキルで全体の状況を確認し、優先度の高いものから着手する:

1. 自分の PR に CHANGES_REQUESTED がある → 修正対応を優先
2. 自分がレビュー依頼されている → レビューを優先  
3. 自分の Issue で期限が近い → 実装を優先

## 完了後

- Issue の場合: PR を作成して `Closes #<N>` を本文に含める
- PR の場合: レビュー対応後に `jj safe-push` または `git push` で push する
