# Plugin全体構成

このMarketplaceは、GitHub Issueを入口にした開発、開発中の知識記録、Zenn記事の作成を分担して提供する。プラグインは互いのフックを暗黙に共有せず、依存する場合はREADMEとこの文書に明記する。

## 責務

| Plugin | 主な責務 | 起動の入口 | 依存・連携 |
| --- | --- | --- | --- |
| `issue-driven-flow` | Issue選定、テスト審査、Red-Green-Refactor、PR | `/issue-driven-flow:start-feature` | `change-driven`のjj運用を参照できる |
| `change-driven` | 1 Change 1責任の計画とjj安全網 | `change-planner` | `jj-exec-aliases`の`safe-*`は任意導入 |
| `obsidian-knowledge` | Vaultまたはローカル受け箱への記録・想起 | `obsidian-capture`、`obsidian-consolidate` | Vault不在時は`.claude/knowledge-inbox/` |
| `zenn-review` | 素材から下書き、レビュー、了承後のMyZenns Issue作成 | `/zenn-review:draft-article` | `UtakataKyosui/MyZenns` |
| 技術別Plugin | Tauri、Protobufなどの技術支援 | 各PluginのSkill | 開発フローとは独立 |

## 標準フロー

```text
GitHub Issue
  → issue-driven-flowで受け入れ条件を整理
  → tdd-test-reviewerがテスト計画を審査
  → jj ChangeごとにRed-Green-Refactor
  → PR
  → SessionSummaryまたはobsidian-knowledgeへ学びを記録
  → zenn-reviewで下書き・レビュー
  → ユーザーが了承
  → MyZennsに記事Issueを作成
```

独立したテーマは、GitHub Issueを開発の入口にせず、`zenn-review:draft-article`へ直接渡せる。MyZennsへのIssue作成はどちらの入口でもユーザーの明示的な了承後に限る。

## フックの共存ルール

- `issue-driven-flow`と`change-driven`を同時に有効化する場合、jj操作をブロックするフックが重複しないか確認する。
- `obsidian-knowledge`の想起フックは失敗時に終了し、開発や執筆をブロックしない。
- `zenn-review`のfrontmatterフックは助言だけを返し、Issue作成や公開を自動実行しない。
- 同じイベントで同じ責務のフックを追加する場合は、先にこの文書とPlugin READMEを更新する。

## バージョンとカテゴリ

各Pluginの`.claude-plugin/plugin.json`と`.claude-plugin/marketplace.json`の`version`を一致させる。バージョンはSemVerで管理し、破壊的変更はメジャー、機能追加はマイナー、修正はパッチを上げる。カテゴリは`workflow`、`development`、`productivity`のいずれかを使う。
