---
description: jj、Lefthook、IssueテンプレートなどIssue起点の開発環境を初期化する。
---

# /issue-driven-flow:init-project

新規リポジトリに issue-driven-flow の全環境を一括セットアップする。

`jj`・Lefthook・スコープマニフェスト・GitHub Issue テンプレート・RTK 確認・Permission を一発で整える。
実行後、すぐに `/issue-driven-flow:start-feature` で Issue ループを開始できる状態になる。

## 実行手順

### Step 1: ツール確認

以下のツールがインストール済みか確認する。不足があれば `harness-setup` エージェントを呼んでインストール手順を案内する。

```bash
which jj || echo "MISSING: jj"
which lefthook || echo "MISSING: lefthook"
which rtk || echo "MISSING: rtk"
which gh || echo "MISSING: gh"
```

### Step 2: jj 初期化

`.jj/` ディレクトリがなければ初期化する:

```bash
# Git リポジトリが既にある場合（推奨）
jj git init --colocate
# または新規の場合
# jj init
```

### Step 3: jj safe-* コマンドの導入（任意）

`jj safe-new` / `jj safe-push` とシェルラッパーは外部ツール
[jj-exec-aliases](https://github.com/UtakataKyosui/jj-exec-aliases) が提供する。
利用する場合は同リポジトリの手順に従って導入する（alias未導入時は同梱hookが素のjjコマンドを許可する）。

### Step 4: GitHub 認証確認

```bash
rtk gh auth status
```

未認証の場合: `gh auth login` をユーザーに促す（インタラクティブのため直接実行しない）。

### Step 5: Lefthook のインストールと設定展開

```bash
# Lefthook がインストール済みか確認
which lefthook || echo "⚠️ lefthook 未インストール: https://github.com/evilmartians/lefthook"
```

プロジェクトルートに `lefthook.yml` が存在しない場合のみコピーする（既存がある場合は diff を提示してユーザーに判断を委ねる）:

```bash
if [[ ! -f lefthook.yml ]]; then
  cp "${CLAUDE_PLUGIN_ROOT}/templates/lefthook.yml" lefthook.yml
  lefthook install
fi
```

### Step 6: スコープマニフェストの準備

`issue-driven-flow:change-planner` に Issue を渡して
`jj safe-new` と共有するスコープマニフェストを生成する。このプラグインから旧式の
`.claude/jj-scope.json` は作成しない。

### Step 7: GitHub Issue テンプレート

`.github/ISSUE_TEMPLATE/` に Issue テンプレートを展開する:

```bash
mkdir -p .github/ISSUE_TEMPLATE
if [[ ! -f .github/ISSUE_TEMPLATE/task.md ]]; then
  cp "${CLAUDE_PLUGIN_ROOT}/templates/ISSUE_TEMPLATE.md" .github/ISSUE_TEMPLATE/task.md
fi
```

### Step 8: RTK 確認

```bash
rtk --version 2>/dev/null || echo "⚠️ RTK 未インストール。トークン最適化が無効です。"
```

### Step 9: 完了サマリ

セットアップ結果をリスト形式で表示する:

```
✅ jj 初期化完了
✅ GitHub 認証済み
✅ Lefthook インストール済み（lefthook.yml 展開済み）
✅ スコープマニフェスト: `issue-driven-flow:change-planner` で生成
✅ GitHub Issue テンプレート展開済み
✅ RTK 利用可能

次のステップ:
1. `gh issue create` でタスク Issue を作成する
2. `/issue-driven-flow:start-feature` で Issue の実装を開始する
```

## 注意事項

- このコマンドは **冪等**。既存ファイルは上書きしない（差分提示のみ）
- `jj git init --colocate` は既存 `.git` リポジトリに jj を追加する（.git は消えない）
- jj 未使用チームのリポジトリに使う場合: `--colocate` で git と共存できる
