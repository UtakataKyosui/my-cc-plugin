---
description: GitHub Issueを選び、jj workspaceと作業Changeを準備する。
---

# /issue-driven-flow:start-feature

Issue を選んで実装を開始するワンストップコマンド。
Issue の選定 → ブランチ命名 → jj workspace / worktree 作成 → 自己アサイン まで一気通貫で行う。

## 実行手順

### Step 1: 未着手 Issue の一覧取得

```bash
rtk gh issue list --assignee "" --state open --json number,title,labels,assignees --limit 20
```

取得した Issue を番号・タイトル・ラベルで整理し、AskUserQuestion で選択させる（最大 4 件をリストアップ。「Other（直接入力）」で任意番号も受け付ける）。

### Step 2: Issue 詳細の確認

選択された Issue 番号で詳細を取得する:

```bash
rtk gh issue view <NNN> --json number,title,body,labels
```

### Step 3: ブランチ名の提案

Issue のタイトルとラベルから Conventional Commits 型の命名を推定し、提案する:

- ラベル `bug` → `fix`
- ラベル `enhancement` / `feature` → `feat`
- ラベル `docs` → `docs`
- ラベル `refactor` → `refactor`
- ラベル `test` → `test`
- それ以外 → `chore`

```
提案: feat/123-add-user-authentication
```

AskUserQuestion でブランチ名を確認（別の名前を入力することも可）。

### Step 4: ワークスペース作成方式の選択

AskUserQuestion で選ぶ:

1. **jj workspace add（推奨）** — jj の並列ワークスペース機能で別ディレクトリを作成。メインの作業を止めずに並行実装できる
2. **カレントディレクトリのまま作業** — シンプルにブランチだけ作成

jj workspace add を選んだ場合:

```bash
jj workspace add ../<ブランチ名> --revision @
cd ../<ブランチ名>
jj bookmark create <ブランチ名> -r @
```

### Step 5: 自己アサインとラベル付与

```bash
rtk gh issue edit <NNN> --add-assignee @me
```

ラベル `in-progress` があれば追加する:

```bash
rtk gh label list --json name | grep -q in-progress && rtk gh issue edit <NNN> --add-label in-progress || true
```

### Step 6: 開始サマリ

```
🚀 Issue #<NNN> の実装を開始しました

  ブランチ: <branch-name>
  ワークスペース: <path>

次のステップ:
1. 実装を進める（1 Change = 1 責任範囲を維持する）
2. Change の実装が終わったら jj safe-new で次の Change へ
3. すべての Change 完了後: /issue-driven-flow:commit-change でコミットメッセージを整備
4. /issue-driven-flow:open-pr で PR を作成する
```

## 注意事項

- jj では jj-exec-aliases 導入時は `jj new` の代わりに `jj safe-new` alias を使う（シェルラッパー導入時は `jj new` も透過リダイレクトされる）。未導入時は通常の `jj new` を使う
- ブランチ名には Issue 番号を必ず含める（`feat/123-slug` 形式）
- マルチタスク時は Step 4 で jj workspace を選ぶことで並列実装ができる
