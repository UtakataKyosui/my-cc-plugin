---
name: branch-cleanup
description: >
  gh poi を使ってマージ済みブランチを検出し、対応する Git worktree / jj workspace ごと整理する。
  以下の場合に使用:
  (1) 「マージ済みブランチを片付けて」「ローカルを掃除して」と指示されたとき
  (2) 「worktree を整理して」「stale branch を削除して」と指示されたとき
  (3) 「cleanup」「prune」「branch 削除」「古いブランチ」というキーワードが含まれるとき
  (4) SessionStart で stale 通知を受けて対応したいとき
version: 0.1.0
---

# branch-cleanup スキル

`gh poi` を使って squash merge 含むマージ済みブランチを検出し、対応する worktree / workspace も連動削除する。

## 前提: gh poi のインストール

```bash
gh extension install seachicken/gh-poi

# アップグレード
gh extension upgrade poi

# インストール確認
gh poi --help
```

## 基本フロー

### Step 1: マージ済みブランチを確認（dry-run）

```bash
rtk gh poi --dry-run
```

削除候補のブランチを表示する。実際には何も削除しない。

### Step 2: 対応する worktree / workspace を確認

**Git worktree:**
```bash
git worktree list --porcelain
```

**jj workspace:**
```bash
jj workspace list
```

対象ブランチに紐づく worktree / workspace を特定する。

### Step 3: 未コミット変更の確認（安全チェック）

各 worktree / workspace に入ってチェックする:

```bash
# git worktree の場合
git -C <worktree-path> status --short

# jj workspace の場合
jj -R <workspace-path> status
```

未コミット変更がある場合は削除 **しない**。

### Step 4: Worktree / Workspace の削除（ブランチ削除より先に実行）

**Git worktree:**
```bash
git worktree remove <path>          # 通常削除
git worktree remove --force <path>  # 強制（注意: 未コミット変更も削除される）
```

**jj workspace:**
```bash
jj workspace forget <name>
```

### Step 5: ブランチ削除（gh poi 本体）

```bash
rtk gh poi
```

dry-run なしで実行するとインタラクティブに削除するブランチを選択できる。

### Step 6: jj リポジトリの同期

jj を使っている場合は bookmarks を同期する:

```bash
jj git import
# または
jj git fetch
```

## 安全策（削除してはいけないもの）

| 対象 | 理由 |
|------|------|
| `main` / `master` / `develop` | デフォルトブランチ |
| 現在チェックアウト中のブランチ | 操作中 |
| 未コミット変更がある worktree | データロスト防止 |
| PR がまだ OPEN のブランチ | gh poi が自動で除外 |

## /branch-cleanup:cleanup-merged コマンド

ブランチ・worktree・workspace の連動削除ワークフロー全体を自動で実行するコマンド。詳細は `/branch-cleanup:cleanup-merged` を参照。
