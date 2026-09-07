---
name: issue-driven-flow-open-pr
description: 現在の jj ブランチから PR を作成する。Issue 番号を自動検出して Closes #NNN を本文に挿入し、Conventional Commits 形式のタイトルを生成する。
argument-hint: "[PR タイトルまたは概要]"
allowed-tools:
  - Bash
  - Read
---

# /issue-driven-flow:open-pr

現在のブランチのコミット差分を解析して PR を作成する。Issue-Driven フローに特化した形式で本文を自動生成する。

## 実行手順

### Step 1: 変更差分の確認

```bash
jj log -r 'trunk()..@' --no-graph
jj diff --stat
```

### Step 2: CI チェック

CI チェックが未実施の場合は `/issue-driven-flow:ci-check` を先に実行することを提案する。

### Step 3: Issue 番号の検出

ブランチ名から Issue 番号を抽出する:

```bash
BRANCH=$(jj log -r @ --no-graph -T 'bookmarks' 2>/dev/null | head -1)
ISSUE=$(echo "$BRANCH" | grep -oE '[0-9]+' | head -1)
```

Issue が見つかった場合: `rtk gh issue view $ISSUE` で Issue の概要を取得してタイトルと本文に活用する。

### Step 4: PR タイトルの生成

引数がある場合はそれを使用。なければ:
1. ブランチ名の type prefix（`feat/` `fix/` 等）から type を抽出
2. Issue タイトルや最新 Change description を参考にタイトルを生成
3. 形式: `<type>: <概要>`

### Step 5: PR 作成

```bash
gh pr create --title "<title>" --body "$(cat <<'EOF'
## 概要

<変更の目的（why）>

## 変更内容

<主な変更点（箇条書き）>

Closes #<ISSUE番号>

🤖 Generated with [Claude Code](https://claude.ai/code) + issue-driven-flow
EOF
)"
```

### Step 6: PR URL の表示

作成した PR URL を表示し、次のステップを案内する:

```
✅ PR #<N> 作成完了
   URL: https://github.com/...

次のステップ:
- レビュー待ち → CI が通ったらレビュアーを追加する
- レビューが届いたら: /issue-driven-flow:respond でレビューに対応する
- コードレビューを自分で行う: /issue-driven-flow:review
```

## 規約チェック

PR 作成前に以下を確認する:
- タイトルが `<type>: <概要>` 形式
- 本文に `Closes #NNN` が含まれている（Issue-Driven 必須）
- 本文に「なぜこの変更が必要か」が記載されている
