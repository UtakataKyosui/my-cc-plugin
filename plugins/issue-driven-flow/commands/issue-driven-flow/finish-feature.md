---
description: PRマージ後にjj workspaceやブランチを整理し、次のタスクを提案する。
---

# /issue-driven-flow:finish-feature

PR のマージ後に後始末（ブランチ・workspace 削除 + 次タスク提案）を行う。

## 実行手順

### Step 1: 現在ブランチの PR 状態を確認

```bash
BRANCH=$(jj log -r @ --no-graph -T 'bookmarks' 2>/dev/null | head -1 || rtk git rev-parse --abbrev-ref HEAD)
rtk gh pr list --head "$BRANCH" --json number,title,state,mergedAt --state all
```

PR が見つからない場合は PR 番号の入力を促す。

### Step 2: マージ確認

PR の `state` が `MERGED` であることを確認する。

まだマージされていない場合:
- レビュー待ち → 「PR #NNN はまだマージされていません。レビューを待つか `/issue-driven-flow:respond` でレビューに対応してください」
- 変更要求あり → `/issue-driven-flow:respond` を案内

### Step 3: Issue のクローズ確認

PR 本文に `Closes #NNN` が含まれているか確認する:

```bash
rtk gh pr view <PR番号> --json body | grep -oE '(Closes|Fixes|Resolves) #[0-9]+'
```

Issue が自動クローズされていない場合は手動クローズを提案（AskUserQuestion で確認してから実行）。

### Step 4: Stale ブランチ・workspace の削除

#### jj workspace の場合

```bash
# メインの workspace に戻ってから
jj workspace forget <ブランチ名>
```

#### git worktree の場合

```bash
rtk git worktree remove <パス>
rtk git branch -d <ブランチ名>
rtk gh poi  # マージ済みリモートブランチも削除
```

gh poi が未インストールの場合:
```bash
rtk gh api repos/{owner}/{repo}/pulls --jq '.[] | select(.state=="closed" and .merged_at != null) | .head.ref' | xargs -I {} rtk gh api -X DELETE repos/{owner}/{repo}/git/refs/heads/{}
```

### Step 5: 次のタスク提案

現在の Open Issue から未着手のものをリストアップして次タスクを提案する:

```bash
rtk gh issue list --assignee "" --state open --json number,title,labels --limit 10
```

優先度ラベル（`priority:high` > `priority:medium` > その他）でソートして提案する。

### Step 6: 完了サマリ

```
✅ PR #<N> マージ済み確認
✅ Issue #<NNN> クローズ済み
✅ ブランチ <branch-name> 削除完了
✅ workspace <path> 削除完了

🎯 次のおすすめ Issue:
  #<NNN1>: <タイトル> [ラベル]
  #<NNN2>: <タイトル> [ラベル]

→ /issue-driven-flow:start-feature で次の実装を開始できます
```

## 注意事項

- `jj workspace forget` は workspace ディレクトリを消すが `.jj` のデータは残る。ディレクトリ自体は `rm -rf` が必要（確認してから実行）
- `gh poi` には `gh extension install seachicken/gh-poi` が必要
- Issue の手動クローズは必ず AskUserQuestion で確認してから実行する（誤クローズ防止）
