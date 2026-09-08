---
description: 現在のjj ChangeからIssue番号付きのConventional Commitsメッセージを起案する。
---

# /issue-driven-flow:commit-change

現在の jj Change に Conventional Commits 形式 + Issue 番号付きのメッセージを設定する。

`conventional-commit-writer` エージェントが diff・ブランチ名・Issue 本文を分析し、適切なコミットメッセージを起案する。

## 実行手順

### Step 1: 変更状態の確認

```bash
jj log -r @ --no-graph -T 'change_id.short() ++ " " ++ description.first_line() ++ "\n"'
jj diff --stat
```

変更が空の場合は「コミットする変更がありません」と伝えて終了する。

### Step 2: conventional-commit-writer エージェントの起動

`conventional-commit-writer` エージェントを呼び出す。エージェントが以下を行う:

1. `jj diff` で変更内容を分析
2. ブランチ名から Issue 番号を抽出
3. 共有リゾルバが返すスコープマニフェストで scope を特定
4. `gh issue view <NNN>` で Issue の文脈を取得
5. Conventional Commits メッセージを起案して返す

### Step 3: メッセージの確認と適用

エージェントが起案したメッセージを表示し、ユーザーに確認を求める（AskUserQuestion は使わず、メッセージを提示してフィードバックを待つ）。

確認後、`jj describe` でメッセージを設定する:

```bash
jj describe -m "<type>(<scope>): <subject> (#NNN)"
```

複数行のメッセージ（body/footer あり）の場合:

```bash
jj describe -m "$(cat <<'EOF'
<type>(<scope>): <subject> (#NNN)

<body>

<footer>
EOF
)"
```

### Step 4: Lefthook バリデーション（オプション）

Lefthook がインストール済みであれば `commit-msg` フックを実行して形式を検証する:

```bash
echo "<コミットメッセージ1行目>" | lefthook run commit-msg --files /dev/stdin 2>/dev/null || true
```

### Step 5: 確認

```bash
jj log -r @ --no-graph -T 'change_id.short() ++ " " ++ description.first_line() ++ "\n"'
```

## コミットメッセージ規約

```
<type>(<scope>): <subject> (#NNN)

<body（任意）>

BREAKING CHANGE: <説明>（任意）
```

| フィールド | ルール |
|---|---|
| type | feat / fix / docs / style / refactor / perf / test / build / ci / chore / revert |
| scope | 共有スコープマニフェストの Change キーを基準。なければ変更ディレクトリ名 |
| subject | 50 文字以内、命令形、末尾ピリオドなし |
| (#NNN) | Issue 番号必須。Lefthook が強制する |

## 注意事項

- `jj describe` は現在の Change の description を書き換えるだけで、新 Change は作らない
- Issue 番号が不明な場合: ブランチ名を確認して手動指定する
- 一時的に Issue 番号なしでコミットしたい場合: `SKIP=commit-msg lefthook run commit-msg`（init 時など）
