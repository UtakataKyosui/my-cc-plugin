---
name: pueue-task
description: Pueue デーモンを使ったバックグラウンドタスクのキュー管理。Mode A（長時間タスクのキューイング・並列制御・ログ監視）と Mode B（複数 Claude Code セッションのジョブキュー dispatch）の2モードを提供する。
when_to_use: 「pueue」「バックグラウンド」「タスクキュー」と指示されたとき。ビルド・テスト・rsync など長時間コマンドを並列管理したいとき。「複数のClaudeに」「並行で」「セッション分散」と指示されたとき。
argument-hint: "[mode]"
allowed-tools: Bash(pueue *) Bash(pueued *)
---

# pueue-task

Pueue (v4+) を使ったタスクキュー管理。長時間タスクの管理と、複数 Claude Code セッションの dispatch（tq 代替）の2モードを提供する。

## 前提

- Pueue がインストールされていること: `brew install pueue`
- `pueued` デーモンが起動していること（このスキルが自動確認・起動する）

## Mode A: 長時間タスク管理

### Step 1: デーモン確認・起動

```bash
pueue status
```

エラーが出た場合はデーモンを起動:

```bash
pueued -d
pueue status
```

### Step 2: タスクをキューに追加

```bash
pueue add -- <command>
```

例:

```bash
pueue add -- mise exec -- pnpm turbo build
pueue add -- rsync -av /src/ /dst/
pueue add -- docker build -t myapp .
```

### Step 3: 並列度の調整（省略可）

デフォルトグループの並列数を変更:

```bash
pueue parallel 3  # 同時3タスク実行
```

カスタムグループで並列管理:

```bash
pueue group add builds
pueue parallel -g builds 2  # builds グループで同時2タスク
pueue add -g builds -- mise exec -- pnpm turbo build --filter=app1
pueue add -g builds -- mise exec -- pnpm turbo build --filter=app2
```

### Step 4: 進捗を監視

全タスクの状況:

```bash
pueue status
```

実行中タスクのリアルタイム出力（tail -f 相当）:

```bash
pueue follow <id>
```

特定タスクの完了まで待機:

```bash
pueue wait <id>
```

### Step 5: 結果を確認

```bash
pueue log <id>
pueue log <id1> <id2>  # 複数タスクまとめて確認
```

### Step 6: クリーンアップ

完了タスクを一括削除:

```bash
pueue clean
```

---

## Mode B: Claude Code セッション dispatch（マルチセッション）

複数の Claude Code セッションをジョブキューで管理する。並列 AI コーディングや大規模タスク分散に使用する。

### Step 1: claude グループを作成

```bash
pueue group add claude
pueue parallel -g claude 3  # 同時3セッションまで
```

### Step 2: タスクを分解してセッションを dispatch

```bash
# --print フラグで非インタラクティブ実行、出力をキューで管理
pueue add -g claude -- claude --print "<タスク指示1>"
pueue add -g claude -- claude --print "<タスク指示2>"
pueue add -g claude -- claude --print "<タスク指示3>"
```

作業ディレクトリを指定する場合:

```bash
pueue add -g claude --working-directory /path/to/project -- claude --print "<指示>"
```

### Step 3: 依存関係のあるタスクを連鎖させる

```bash
# タスク1が成功した後にタスク2を実行
TASK1=$(pueue add -g claude -- claude --print "実装: ユーザー認証モジュール" | grep -oE '[0-9]+')
pueue add -g claude --after $TASK1 -- claude --print "テスト: ユーザー認証モジュールのテスト作成"
```

### Step 4: 全セッションの進捗を監視

```bash
pueue status -g claude
```

### Step 5: 各セッションの出力を確認

```bash
pueue log <id>
```

### Step 6: 完了後のクリーンアップ

```bash
pueue clean -g claude
```

---

## よく使うコマンド早見表

| 目的 | コマンド |
|------|---------|
| タスク追加 | `pueue add -- <cmd>` |
| 全状況確認 | `pueue status` |
| リアルタイム監視 | `pueue follow <id>` |
| ログ確認 | `pueue log <id>` |
| タスク一時停止 | `pueue pause <id>` |
| タスク再開 | `pueue start <id>` |
| タスク強制終了 | `pueue kill <id>` |
| 完了タスク削除 | `pueue clean` |
| 全リセット | `pueue reset` |
| デーモン停止 | `pueue shutdown` |

## 注意事項

- `pueued` は永続デーモン。Claude Code セッション終了後も継続動作する
- デーモンはリソースを消費するため、長期不使用時は `pueue shutdown` で停止を検討
- `claude --print` フラグは非インタラクティブモードで出力を stdout に返す
- Pueue フック (`pueue-daemon-guard.sh`) がデーモン未起動を検出すると自動通知する
