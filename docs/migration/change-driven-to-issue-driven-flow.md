# change-driven から issue-driven-flow への移行

> **この文書は v0.3.0 時点の記録です。** v0.4.0（Issue #82）で jj 安全網と Change 計画は
> `change-driven@jj-exec-aliases` へ移管され、下表の対応関係は逆向きになりました。
> 現在の構成は `plugins/issue-driven-flow/README.md` の「前提条件」を参照してください。

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
