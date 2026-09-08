# change-driven から issue-driven-flow への移行

`change-driven` は `issue-driven-flow` v0.3.0 に統合されました。今後は統合先だけをインストールします。

```text
/plugin install issue-driven-flow@my-cc-plugin
```

既存の `change-driven` を有効にしている環境では、重複hookを避けるため先に無効化または削除してください。
その後、`issue-driven-flow` を有効化します。Agentの呼び出し名は次のように変わります。

| 旧 | 新 |
|---|---|
| `change-driven:change-planner` | `issue-driven-flow:change-planner` |
| `change-driven:conventional-commit-writer` | `issue-driven-flow:conventional-commit-writer` |

`jj safe-new` / `jj safe-push` は引き続き任意の `jj-exec-aliases` が提供します。aliasを導入している場合は
統合Pluginのhookが直接実行をブロックし、未導入の場合は通常の `jj new` / `jj git push` にフォールバックします。
