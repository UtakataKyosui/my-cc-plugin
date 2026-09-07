---
name: pr-review-format
description: >
  PR のコードレビューを正しいフォーマットで投稿するスキル。
  以下の場合に使用:
  (1) PR のコードレビューをするとき
  (2) gh api で reviews エンドポイントを呼ぶとき
  (3) 「レビューする」「PR を確認する」「PR を見る」「コードレビュー」と指示されたとき
  必須フォーマット: top-level body に「適正な実装」「修正することが望ましいところ」の両セクションを含め、
  個別の指摘は suggestion ブロック付きインラインコメントとして投稿する。
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "bash \"${CLAUDE_PLUGIN_ROOT}/skills/pr-review-format/scripts/review-format-check.sh\""
---

# PR レビューフォーマット

## event の選択ルール

| 修正セクションの内容 | event |
|---|---|
| 空または「なし」のみ | `APPROVE` |
| 1 件以上の修正項目あり | `REQUEST_CHANGES` |

`gh api` の `event` フィールドにこの値を設定する。`COMMENT` は使わない。

## 構成

PR レビューは **2 段構成** で投稿する。

### 段 1: top-level body（必須）

最初のレビューコメント（`gh api .../reviews` の `body` フィールド）に以下の構造を使う。

```markdown
## 適正な実装

- 具体的に良い点を 1 行ずつ列挙

## 修正することが望ましいところ

- 修正が必要な点を 1 行ずつ列挙（対応するインラインコメントに詳細あり）
```

両セクションとも必ず記載する。指摘が 0 件の場合は `なし` と書く。

### 段 2: インラインコメント（suggestion 付き）

個別の修正指摘は `comments` 配列でインラインコメントとして追加する。
コード変更を伴う場合は必ず ` ```suggestion ` ブロックを使う。

コメントプレフィックス: `[must]` 必須 / `[imo]` 意見 / `[nits]` 細かい指摘 / `[ask]` 質問

````markdown
[must] 変数名が曖昧です。

```suggestion
const filteredItems = items.filter(Boolean);
```
````

## 投稿コマンド例

```bash
gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews \
  --method POST \
  --input - <<'EOF'
{
  "body": "## 適正な実装\n\n- テストカバレッジが充実している\n\n## 修正することが望ましいところ\n\n- 変数名を修正（詳細はインラインコメント参照）",
  "event": "REQUEST_CHANGES",
  "comments": [
    {
      "path": "src/index.ts",
      "line": 42,
      "body": "[must] 変数名が曖昧です。\n\n```suggestion\nconst filteredItems = items.filter(Boolean);\n```"
    }
  ]
}
EOF
```

Python ヘルパーを使ってフォーマット検証してから投稿する場合:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/pr-review-format/scripts/post_review.py" \
  --repo owner/repo \
  --pr 123 \
  --validate-only <<'EOF'
{
  "body": "...",
  "event": "REQUEST_CHANGES",
  "comments": [...]
}
EOF
```

## 禁止事項

- top-level body に「適正な実装」「修正することが望ましいところ」のどちらかが欠けたまま投稿する
- コード変更の提案を suggestion ブロックなし（plain テキストのみ）で行う
- top-level body なしでインラインコメントだけ投稿する
