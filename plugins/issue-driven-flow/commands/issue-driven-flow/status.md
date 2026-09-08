---
description: jj、GitHub Issue、PR、CIの現在状態をまとめて確認する。
---

# /issue-driven-flow:status

現在の jj/Issue/PR/CI の状況を 1 コマンドで俯瞰するダッシュボード。

セッション開始時や迷子になったときに実行して、今どこにいるかを把握する。

## 実行手順

以下を並列で取得してサマリを表示する:

### VCS 状態

```bash
jj log --limit 5 --no-graph -T 'change_id.short() ++ " " ++ bookmarks ++ " " ++ description.first_line() ++ "\n"'
```

### 現在のブランチ・workspace

```bash
jj workspace list 2>/dev/null || true
jj log -r @ --no-graph -T 'bookmarks'
```

### 未コミット変更

```bash
jj diff --stat
```

### 自分の進行中 PR

```bash
rtk gh my-task -j 2>/dev/null | head -50 || rtk gh pr list --author @me --state open --json number,title,reviewDecision,isDraft
```

### CI 状態（現ブランチ）

```bash
BRANCH=$(jj log -r @ --no-graph -T 'bookmarks' 2>/dev/null | head -1)
[[ -n "$BRANCH" ]] && rtk gh pr checks --watch=false 2>/dev/null | head -20 || true
```

### 担当 Issue

```bash
rtk gh issue list --assignee @me --state open --json number,title,labels --limit 5
```

## 表示フォーマット

```
=== issue-driven-flow: Status ===

📌 現在地
  ブランチ: feat/123-user-auth
  Workspace: /path/to/workspace
  未コミット変更: 3 ファイル

📋 担当 Issue
  #123  feat: ユーザー認証機能を追加 [in-progress]
  #456  fix: ログアウト後のセッション残留 [high-priority]

🔀 進行中 PR
  #78   feat: ユーザー認証 → REVIEW_REQUIRED
  #65   fix: セッションバグ修正 → CHANGES_REQUESTED

🔬 CI 状態（PR #78）
  ✅ lint    ✅ typecheck    ❌ test (2 failed)

💡 次のアクション
  - CI 失敗: /issue-driven-flow:ci-check で詳細確認
  - レビュー対応: /issue-driven-flow:respond
  - 次 Issue: /issue-driven-flow:start-feature
```

## 注意事項

- `gh my-task` 拡張が未インストールの場合は `gh pr list` にフォールバックする
- `jj workspace` が使えない環境（jj 未使用）では git ブランチ情報を代わりに表示する
- CI 状態は現在の @ Change が push 済みの場合のみ表示される
