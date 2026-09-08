# pueue-queue

Pueue（デーモン型ジョブキュー）を使うためのプラグイン。長時間タスクの管理と、複数 Claude Code セッションの dispatch の2用途を扱う。

## 構成

| 種別 | 名前 | 役割 |
|---|---|---|
| Skill | `pueue-queue:pueue-task` | キューイング・並列制御・ログ監視（Mode A）と、セッション dispatch（Mode B） |
| Hook | `PreToolUse` / Bash | `pueue` を含むコマンドの実行前に `pueued` の稼働を確認し、未起動なら通知する。ブロックはしない |
| Docs | `docs/pueue.md` | いつ Pueue を使うかの判断基準。行動ルールとして利用者側から参照する |

## 行動ルールの読み込み

プラグインは `rules/` を読み込まない。`docs/pueue.md` の内容を常に効かせたい場合は、利用者側の `~/.claude/rules/pueue.md` にこのファイルへのポインタを置く。

## 依存

- `pueue` / `pueued`（未インストールならフックは何もしない）
- `jq`
