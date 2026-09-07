# my-cc-plugin

個人用 Claude Code プラグインを一元管理・配布する Marketplace です。

## Plugins

| Plugin | Purpose |
| --- | --- |
| `change-driven` | jj の change-driven 開発フロー |
| `issue-driven-flow` | Issue 起点の開発・PR ワークフロー |
| `obsidian-semantic-search` | Obsidian Vault のローカル意味検索 |

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
