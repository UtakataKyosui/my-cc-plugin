# Safe Push ワークフロー

`jj git push` の直接実行を避け、diverge チェック → conflict チェック → 品質チェック → dry-run → push の安全なワークフローを通す仕組み。

## なぜ safe-push が必要か

jj はコミットの書き換えを前提とした VCS のため、`jj git push` 時にリモートと異なるコミットがあると自動的に force-push する。これにより、他者がリモートに push した変更を上書きするリスクがある。

## 基本的な使い方

```bash
# 通常の push（確認プロンプトあり）
jj safe-push

# 特定 bookmark のみ push
jj safe-push -b feat/my-feature

# 確認をスキップして push
jj safe-push --yes

# dry-run のみ（push しない）
jj safe-push --dry-run
```

`jj safe-push` の実行フロー:

1. `@..remote_bookmarks()` で diverge チェック → 未 fetch なら exit 1
2. `conflicts()` で conflict チェック → conflict があれば exit 1
3. `lefthook run pre-push` → 失敗で exit 1（`lefthook.yml` 存在時のみ）
4. `jj git push --dry-run` で内容確認
5. 対話確認（tty かつ `--yes` なしの場合）
6. `jj git push` で本実行

## セットアップ

`jj safe-push` / `jj safe-new` は外部ツール
[jj-exec-aliases](https://github.com/UtakataKyosui/jj-exec-aliases) が提供する。
同リポジトリの手順に従って jj alias を登録すると `jj safe-push` が使えるようになる。
ターミナルでの `jj new` / `jj git push` を `jj safe-*` へリダイレクトするシェルラッパーも
jj-exec-aliases が提供する。

> このプラグインは以前 `scripts/jj-safe-push.sh` ＋ `install-jj-aliases.sh` ＋
> シェルラッパーを同梱していたが、安全網一式を jj-exec-aliases に集約した（Issue #19）。

## ガード機構（二重防御）

> 安全網一式は外部ツール [jj-exec-aliases](https://github.com/UtakataKyosui/jj-exec-aliases) に集約済み。
> jj 専用の PreToolUse Hook やプラグイン同梱スクリプトは持たず、ガードは jj alias と
> シェルラッパー（いずれも jj-exec-aliases 提供・opt-in）の二層で担う。

### 1. jj aliases（主防衛線）

`jj safe-push` は jj alias として登録され、インストールしたすべての環境で有効:

- `bypassPermissions` モードでも alias は維持される（Claude Code に依存しない）
- `jj safe-new` / `jj safe-push` を経由することで品質チェックが必ず実行される

### 2. シェル関数ラッパー（ターミナル操作をガード）

jj-exec-aliases のシェルラッパーがシェル関数として `jj` コマンドをラップ:

- `jj new` → `jj safe-new` に透過リダイレクト（エラーなし）
- `jj git push` → `jj safe-push` に透過リダイレクト（エラーなし）
- その他 → `command jj` にパススルー

## jj コマンドの直接バイパス

スクリプト内など、安全が確認された状況でガードを無効化する:

```bash
# shell wrapper をバイパス（safe-* リダイレクトを回避して素の jj を実行）
command jj git push
command jj new -m "message"
```

## diverge の解消

conflicted bookmark が検出された場合:

1. `jj git fetch` でリモートの最新を取得
2. `jj log` で状況を確認
3. `jj rebase -b <bookmark> -d <target>` でローカルをリモートの上に rebase
4. `jj bookmark list --conflicted` で解消を確認
