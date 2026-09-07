---
description: SessionSummary、Obsidianノート、または指定テーマからZenn記事の下書きを作成し、レビューと修正まで行う。Issueは作成しない。
---

# /zenn-review:draft-article

開発で得た学び、SessionSummary、Obsidian Vaultのノート、または独立したテーマを材料に、Zenn記事の下書きを作成する。記事案の確認前にGitHub Issueを作成してはならない。

## 手順

1. 材料の所在を確認する。読めないVaultやSessionSummaryは推測で補わず、不足として記録する。
2. 主張、対象読者、読者が記事を読んだ後にできることを整理する。
3. タイトル案、概要、アウトライン、参考資料、検証が必要なコード例を作る。
4. `articles/<slug>.md` または作業用のMarkdownとして下書きを作成する。Zennのfrontmatterを含める。
5. `zenn-reviewer` を起動し、frontmatter、構文、誤字脱字、内容の正確性・完全性・一貫性をレビューする。
6. 指摘を修正し、再レビューする。Mermaid図がある場合は描画結果も確認する。
7. 次の確認ブロックを出力して停止する。

```text
記事案の確認
タイトル: ...
対象読者: ...
概要: ...
下書き: ...
レビュー結果: ...

この内容でMyZennsに記事Issueを作成してよいですか？
```

ユーザーが明示的に了承したら `/zenn-review:create-myzenns-issue` を実行する。

## 文体

MyZennsの運用に合わせ、結論を先に書き、抽象的な名詞を動詞に置き換え、同じ内容を繰り返さない。日本語の強調に太字や括弧書きを多用しない。
