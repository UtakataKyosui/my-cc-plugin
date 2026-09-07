---
description: ユーザーが記事案を確認して明示的に了承した後、下書きとレビュー結果からMyZennsに記事Issueを作成する。
---

# /zenn-review:create-myzenns-issue

`/zenn-review:draft-article` が出力した記事案について、ユーザーの明示的な了承を受けた後だけ実行する。了承が確認できない場合はIssueを作成せず、確認を求める。

## 手順

1. 対象リポジトリを確認する。既定値は `UtakataKyosui/MyZenns`、変更する場合は `MYZENN_REPO` を使う。
2. 記事案からタイトル、概要、対象読者、アウトライン、参考資料、素材の所在、レビュー結果をIssue本文に整形する。
3. `zenn` と `article` ラベルが存在することを確認する。存在しない場合はラベル作成を提案して停止する。
4. 次のコマンドでIssueを作成する。本文は一時ファイルに書き、シェル引数へ直接埋め込まない。

```bash
gh issue create \
  --repo "${MYZENN_REPO:-UtakataKyosui/MyZenns}" \
  --title "[Zenn:記事] <タイトル>" \
  --label zenn --label article \
  --body-file <一時ファイル>
```

5. 作成されたIssue URLを報告し、下書きの保存場所とレビュー結果を併記する。

Issue本文はMyZennsのテンプレートに合わせる。

```markdown
## 概要
## 対象読者
## アウトライン
## 参考資料・リンク
## 素材の所在
## レビュー結果
## 進行タスク
- [ ] アウトライン作成
- [ ] 下書き作成
- [ ] 自己レビュー
- [ ] 公開準備
- [ ] Zennへ公開
```
