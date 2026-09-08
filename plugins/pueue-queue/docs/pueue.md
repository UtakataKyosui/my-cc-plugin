# Pueue タスクキュー

Pueue はデーモン型ジョブキュー。長時間タスクの管理と、複数 Claude Code セッションの dispatch（ジョブキュー）の2用途で使う。

## ルール

- **長時間コマンド**（ビルド・テスト全件・rsync・docker build 等）は `run_in_background: true` ではなく Pueue でキューイングすることを検討する。Pueue はセッションをまたいで結果が残り、後から `pueue log <id>` で確認できる
- **マルチ Claude セッション**を並列実行したい場合は `/pueue-task` スキルの Mode B を使う
- `pueue` コマンドを実行する前に `pueued` デーモンが起動しているか確認する（フックが自動で通知する）
- デーモンはセッション終了後も継続動作するため、長期不使用時は `pueue shutdown` で停止する

## 基本操作

```bash
pueued -d                              # デーモン起動
pueue add -- <command>                 # タスク追加
pueue status                           # 全タスク確認
pueue follow <id>                      # リアルタイム監視
pueue log <id>                         # ログ確認
pueue clean                            # 完了タスク削除
```

## Claude セッション dispatch（tq 代替）

```bash
pueue group add claude
pueue parallel -g claude 3
pueue add -g claude -- claude --print "<指示>"
pueue status -g claude
```
