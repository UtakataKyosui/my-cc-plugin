---
name: my-task
description: >
  gh my-task を使って現在のリポジトリで自分が関わる PR の状況を一覧・整理して報告する。
  以下の場合に使用:
  (1) 「今自分が関わっている PR を教えて」「my-task で PR を確認して」と指示されたとき
  (2) 「レビュー待ちの PR は？」「自分の PR の状況を確認して」と指示されたとき
  (3) 「gh my-task」「my task」「PR 一覧」「タスク確認」というキーワードが含まれるとき
  (4) 何を次に着手すべきか判断したいとき
version: 1.0.0
---

# my-task スキル

`gh my-task` 拡張を使って自分が関わる PR の現状を把握し、優先対応を判断する。

## 基本フロー

### 1. PR 一覧取得

```bash
rtk gh my-task -j -R
```

- `-j`: JSON 出力（AI・スクリプト連携用）
- `-R`: レビュー状況を同時取得

### 2. 状況の分類と優先度判断

取得した JSON を以下の優先度で分類する:

| 優先度 | 状態 | 対応 |
|--------|------|------|
| 🔴 高 | 自分の PR に CHANGES_REQUESTED | `gh my-task prompt <N>` でレビュー対応 |
| 🟠 中 | 自分がレビューリクエストされている | PR を確認してレビュー実施 |
| 🟡 低 | 自分の PR が REVIEW_REQUIRED | レビュワーを待つ |
| ⚪ 情報 | APPROVED / merged / draft | 特に対応不要 |

### 3. 個別 PR の詳細確認

```bash
rtk gh pr view <N>           # PR の詳細表示
rtk gh my-task prompt <N>    # レビュー対応 Markdown プロンプトを取得
```

### 4. PR の close（確認後）

```bash
gh my-task close <N>        # 番号入力確認あり
```

## よく使うフィルタ

```bash
rtk gh my-task -j -a         # 自分が author のみ
rtk gh my-task -j -r         # レビュー依頼のみ
rtk gh my-task -j -s closed  # close 済み
```

## 出力の読み方（JSON フィールド）

| フィールド | 意味 |
|-----------|------|
| `number` | PR 番号 |
| `title` | PR タイトル |
| `state` | `open` / `closed` / `merged` |
| `reviewDecision` | `APPROVED` / `CHANGES_REQUESTED` / `REVIEW_REQUIRED` |
| `reviews` | レビュワーと状態の一覧 |

## レポート形式

一覧を取得したら以下の形式で報告する:

```
## 現在の PR タスク状況

### 要対応（CHANGES_REQUESTED）
- #123 タイトル — 修正リクエストあり（レビュワー: @foo）

### レビュー依頼中（自分がレビューリクエストされている）
- #456 タイトル — @bar がリクエスト

### レビュー待ち（自分の PR、レビュアー未応答）
- #789 タイトル — Draft / REVIEW_REQUIRED

合計: N 件
```
