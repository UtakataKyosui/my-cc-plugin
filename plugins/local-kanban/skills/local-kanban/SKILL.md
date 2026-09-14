---
name: local-kanban
description: ローカルファイルベースのカンバンボード管理ツール。外部サービス不要で .kanban/board.json にデータを保存し、タスクの追加・移動・表示・削除を Python スクリプトで操作する。
when_to_use: 「カンバンに追加して」「タスクを作成して」「ボードを見せて」「作業中のタスクを in-progress に移動」「完了した」「カンバン」「kanban」「タスク管理」「ボード」などと指示されたとき。
argument-hint: "[command] [args]"
allowed-tools: Bash(python3 *)
---

# Local Kanban

`scripts/kanban.py` を使ってローカルのカンバンボードを操作する。

データは現在のディレクトリの `.kanban/board.json` に保存される。

## コマンド一覧

```bash
SCRIPT="python3 ${CLAUDE_PLUGIN_ROOT}/skills/local-kanban/scripts/kanban.py"

# 初期化（初回のみ）
$SCRIPT init

# Issue 追加
$SCRIPT add --title "タイトル" --description "説明" --priority high --labels bug

# ボード表示（全列）
$SCRIPT board

# Issue 一覧（列フィルタ可）
$SCRIPT list --column todo   # todo | in-progress | done

# Issue 詳細
$SCRIPT show 1

# 列の移動
$SCRIPT move 1 in-progress   # todo | in-progress | done

# Issue 更新
$SCRIPT update 1 --title "新タイトル" --priority low

# Issue 削除
$SCRIPT delete 1
```

## オプション

- `--priority`: `low` / `medium`(default) / `high`
- `--labels`: スペース区切りで複数指定可 (`--labels bug frontend`)
- `--json`: 全コマンドに付与可。JSON 出力でプログラム的に扱える

## ワークフロー

1. 新しいプロジェクトでは `init` を実行してボードを初期化する
2. Issue は常に `todo` 列に作成される
3. 作業開始時に `move <id> in-progress`、完了時に `move <id> done`

## 注意

- `.kanban/board.json` はバージョン管理に含めてよい（プロジェクトスコープ）
- 外部サービス・インターネット接続不要
- Python 3.8+ 標準ライブラリのみ使用（追加インストール不要）
