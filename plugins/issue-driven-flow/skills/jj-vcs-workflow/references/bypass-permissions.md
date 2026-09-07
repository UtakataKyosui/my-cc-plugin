# bypassPermissions モードでの運用

## 概要

Claude Code を `--dangerously-skip-permissions`（`bypassPermissions` モード）で起動すると、
**Hook を含むすべての権限チェックが無効**になる。

このプラグインは jj 専用 Hook を持たない（Issue #19 で削除済み）。jj のガードは
**jj alias とシェルラッパー**で行うため、`bypassPermissions` モードでも維持される。

## 影響範囲

| 機能 | 通常モード | bypassPermissions |
|---|---|---|
| `jj safe-new`（jj aliases） | ✓ 有効 | ✓ **有効**（Hook ではなく alias のため） |
| `jj safe-push`（jj aliases） | ✓ 有効 | ✓ **有効** |
| シェルラッパー（jj-exec-aliases 提供） | ✓ 有効（導入時） | ✓ **有効**（導入時） |

## 設計上の防衛線

安全網一式は外部ツール [jj-exec-aliases](https://github.com/UtakataKyosui/jj-exec-aliases) に集約されており、
**jj aliases を第一防衛線** とする設計は維持される。

`bypassPermissions` モードで Hook が無効になっても:
- `jj aliases.safe-new` → jj-exec-aliases のリダイレクトは維持される
- `jj aliases.safe-push` → jj-exec-aliases のリダイレクトは維持される

**重要**: jj は `new`, `git push` などの**組み込みコマンドを aliases で上書きできない**。
`aliases.new = [...]` を設定しても jj 本体の `new` が優先されるため効果がない。

そのため `jj new` の直接実行ガードは、全モード共通で **jj-exec-aliases のシェルラッパー**が担う（opt-in）。

`bypassPermissions` 環境で完全なガードが必要な場合は、jj-exec-aliases のシェルラッパーを必ずインストールする。

## 推奨設定

`bypassPermissions` を使う場合は `dontAsk` モードの使用を検討する:

```bash
claude --permission-mode dontAsk
```

`dontAsk` モードは `deny` ルールが維持されるため、誤操作の抑止に有効。

## 参考

- [Permission modes — Claude Code](https://code.claude.com/docs/ja/permission-modes)
- [Permissions — Claude Code](https://code.claude.com/docs/ja/permissions)
- [Hooks reference — Claude Code](https://code.claude.com/docs/en/hooks)
