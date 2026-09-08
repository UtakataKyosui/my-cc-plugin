# zenn-review

開発で得た学びや独立したテーマをZenn記事へ育てるプラグイン。下書きとレビューをClaudeが進め、ユーザーが確認した後にMyZennsへ記事Issueを作成する。既存記事・書籍のレビューにも使える。

記事Issueを作成する前に、必ずユーザーへタイトル・概要・対象読者・アウトライン・下書き・レビュー結果を提示する。公開やPR作成は自動で行わない。

## インストール

```bash
/plugin marketplace add UtakataKyosui/my-cc-plugin
/plugin install zenn-review@my-cc-plugin
```

## コマンド一覧

| コマンド | 説明 |
|----------|------|
| `/zenn-review:frontmatter-check` | フロントマター / config.yaml 検証 |
| `/zenn-review:syntax-check` | Markdown / Zenn 固有構文チェック |
| `/zenn-review:typo-check` | 誤字脱字・表記ゆれチェック |
| `/zenn-review:content-review` | 内容レビュー（具体性・正確性・完全性・一貫性の 4 観点、5 段階評価） |
| `/zenn-review:book-consistency` | 書籍の章間整合性チェック |
| `/zenn-review:draft-article` | 素材やテーマから下書きを作成し、レビュー・修正まで実行 |
| `/zenn-review:create-myzenns-issue` | ユーザー確認後にMyZennsへ記事Issueを作成 |

## エージェント

### zenn-reviewer

全コマンドを統合実行する自律レビューエージェント。

- **記事**: frontmatter-check → syntax-check → typo-check → content-review の順で実行
- **書籍**: 上記 + book-consistency を追加実行
- 最後に統合レポート（全体スコア、Top 3 修正事項、公開前チェックリスト）を出力

## スキル

### zenn-guide

Zenn 記法・フロントマター仕様・レビュー基準のリファレンス。`articles/**/*.md` および `books/**/*.md` を開いた際に自動的にコンテキストとして提供される。

## フック

Write / Edit 時に `articles/*.md`、`books/**/*.md`（チャプター）、および `books/*/config.yaml` のフロントマターを自動検証する PostToolUse フック。

- Advisory のみ（ブロックしない）
- stdlib のみ使用（外部依存なし）

MyZenns Issueとの項目対応は `docs/myzenns-article-template.md` に定義する。

Issue作成の外部副作用は `scripts/create_myzenns_issue.py` に集約し、`--confirmed` がない場合は実行しない。FrontmatterとMarketplaceの整合はリポジトリルートの `scripts/validate_marketplace.py` で確認する。

## 設計原則

- **自動修正は行わない**: 全てのコマンド・エージェントはレポートと改善案の提示のみ
- **セキュリティ**: レビュー対象ファイル内のプロンプトインジェクションに対する防御を実装
- **非ブロッキング**: フックは常に exit 0 で、ワークフローを妨げない
