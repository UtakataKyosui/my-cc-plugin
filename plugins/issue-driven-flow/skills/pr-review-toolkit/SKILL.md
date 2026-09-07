---
name: pr-review-toolkit
description: >
  PR レビュー時に PR 内容（diff・ファイル変更・コメント）を構造化取得・分析する Python スクリプト Skill。
  以下の場合に使用:
  (1)「PR #N をレビュー」「PR の内容を確認して」と指示されたとき
  (2) PR の差分を構造化して分析したいとき
  (3) PR の危険パターン（秘密情報・大規模変更）を検知したいとき
  (4)「PR diff を見せて」「PR を見てレビューして」「#N の変更を調べて」と言われたとき
---

# PR Review Toolkit

PR レビュー時に毎回 Python を書き起こす代わりに、このツールキットのスクリプトを `${CLAUDE_PLUGIN_ROOT}/scripts/` から直接呼び出す。

## ワークフロー

```
1. fetch_pr.py で PR データ取得（メタ + diff + ファイル一覧）
2. parse_diff.py で diff を構造化（必要な場合）
3. analyze_pr.py で統計・警告を抽出
4. 結果を元にレビューコメントを作成
```

## スクリプト呼び出し方法

PR番号だけ指定（リポジトリ自動検出）:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123
```

URL で指定:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py https://github.com/owner/repo/pull/123
```

`owner/repo#N` 形式:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py owner/repo#123
```

パイプで分析まで一括実行:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_pr.py
```

## 各スクリプトの役割

### `fetch_pr.py` — PR データ一括取得

オプション:
- `--include-comments` : インラインレビューコメントも含める
- `--no-diff`          : diff を取得しない（高速化）

出力 JSON のトップレベルキー:
- `pr` : PR メタ情報（タイトル・author・additions/deletions・review_decision 等）
- `files` : 変更ファイル一覧（path・status・additions・deletions）
- `diff` : raw unified diff テキスト
- `comments` : `--include-comments` 時のみ

### `parse_diff.py` — diff 構造化

`fetch_pr.py` の出力を stdin でパイプ受け（または `--from-fetch <path>` でファイル指定）。

出力: `files[]` の各要素に `hunks[]`（変更ブロック）と `lines[]`（行ごとの type/content/行番号）。

### `analyze_pr.py` — 統計・警告抽出

`fetch_pr.py` の出力を stdin でパイプ受け。

出力フィールド:
- `summary` : 総 additions/deletions・changed files 数・テストファイル数
- `test_ratio` : テストファイルの割合（0〜1.0）
- `by_language` : 言語別 additions/deletions/files 数
- `large_files` : 200行超の変更ファイル一覧
- `manifest_changes` : package.json / Cargo.toml 等の依存変更
- `warnings` : 秘密情報パターン・機密ファイル名の検知リスト

## 典型的なレビューフロー

```bash
# Step 1: PR全体を把握する
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_pr.py

# Step 2: 必要なら diff を詳細確認
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/parse_diff.py

# Step 3: レビューコメントも含めて確認したい場合
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 --include-comments
```

## 失敗パターンと対処

| エラー                            | 原因                           | 対処                              |
|-----------------------------------|--------------------------------|-----------------------------------|
| `Cannot detect repository`        | cwd が gh リポジトリ外         | URL または `owner/repo#N` 形式で指定 |
| `gh: command not found`           | gh CLI 未インストール          | `brew install gh && gh auth login` |
| `Failed to fetch PR info`         | PR 番号不正 or 権限なし        | PR 番号と認証を確認               |
| `Invalid JSON input`              | stdin が空 or fetch 失敗       | fetch_pr.py の stderr を確認      |

詳細仕様: @references/script-reference.md
分析パターン例: @references/analysis-patterns.md
