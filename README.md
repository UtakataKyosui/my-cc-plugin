# my-cc-plugin

個人用 Claude Code プラグインを一元管理・配布する Marketplace です。

## Plugins

| Plugin | Purpose |
| --- | --- |
| `change-driven` | jj の change-driven 開発フロー |
| `issue-driven-flow` | GitHub Issue 起点、jj標準、テスト審査付きの開発・PR ワークフロー |
| `obsidian-semantic-search` | Obsidian Vault のローカル意味検索 |
| `scaffdog-colocation` | scaffdog によるコロケーション設計支援 |
| `wasm-optimizer` | JS/TS 処理の WASM 化候補を検出 |
| `activitypub-c2s` | ActivityPub C2S 実装ガイド |
| `protobuf-tools` | Protocol Buffers と buf/protoc の利用支援 |
| `moon-proto` | Moonrepo と proto のツールチェーン支援 |
| `poml-assist` | POML の作成・検証・レンダリング支援 |
| `zenn-review` | 学びやテーマからZenn下書きを作り、確認後にMyZennsのIssueへ登録 |
| `tauri-plugin-dev` | Tauri v2 プラグイン開発支援 |
| `tauri-app-dev` | Tauri v2 アプリケーション開発支援 |
| `obs-plugin-dev` | OBS Studio プラグイン開発支援 |
| `obsidian-knowledge` | Obsidian Vault を使った長期記憶管理 |
| `mise` | mise によるツールバージョン管理支援 |
| `color-distance` | 色差・WCAG コントラストの評価 |
| `plugin-overlap-auditor` | プラグイン内の役割重複の監査 |

## Install

Claude Code で Marketplace を追加します。

```bash
/plugin marketplace add UtakataKyosui/my-cc-plugin
```

次に必要なプラグインをインストールします。

```bash
/plugin install change-driven@my-cc-plugin
```

## Repository layout

各プラグインは `plugins/<plugin-name>` に配置し、Marketplace 定義は
`.claude-plugin/marketplace.json` で管理します。新しいプラグインの追加や更新は、この
リポジトリを唯一の配布元として行います。
