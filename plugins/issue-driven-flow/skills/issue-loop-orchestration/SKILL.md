---
name: issue-loop-orchestration
description: >
  1 Issue の実装ループ（着手 → 実装 → コミット → PR → レビュー → マージ）の
  各局面でどの Claude コマンド・スキル・エージェントを呼ぶべきかを示す詳細ガイド。
  「次に何を呼べばいいか」を迷ったときに参照する。
---

# Issue ループ オーケストレーション

1 つの Issue が完了するまでの詳細な局面ごとのガイド。

## 局面 0: Issue 選定

**トリガー**: 何か実装したい、または新セッション開始時

1. `/issue-driven-flow:status` で現在地を確認
2. `my-task` スキルで担当 Issue と PR を一覧
3. `/issue-driven-flow:start-feature` で Issue を選んで着手宣言

## 局面 1: 実装準備

**トリガー**: `start-feature` 完了後

1. `change-driven:change-planner` エージェント（別途 `change-driven` が必要）がスコープマニフェストを生成済み
2. `code-exploration` スキルで関連ファイルを探索（fd / rg を活用）
3. `context-generation` スキルで repomix コンテキストを生成（必要に応じて）
4. TaskCreate で Change ごとのタスクを登録

## 局面 2: 実装（Change 駆動）

**トリガー**: 実装中

- 1 Change の実装が完了したら `jj safe-new` で次の Change へ
- スコープ外変更が発生したら `jj-vcs-workflow` スキルの `scope-manifest.md` を参照
- 並列タスクがある場合: `parallel-execution` スキルで rust-parallel を活用

## 局面 3: コミット整備

**トリガー**: 全 Change の実装完了後

1. `/issue-driven-flow:commit-change` で各 Change のメッセージを確認・整備
2. `change-driven:conventional-commit-writer` エージェントがメッセージを起案
3. Lefthook `commit-msg` が `<type>(<scope>): <subject> (#NNN)` 形式を強制

## 局面 4: CI チェック

**トリガー**: push 前

1. `/issue-driven-flow:ci-check` でローカル検証
   - TypeScript: tsc --noEmit
   - Python: ruff / mypy
   - Rust: cargo check / cargo clippy
2. エラーがあれば修正してから次へ

## 局面 5: Push と PR 作成

**トリガー**: CI チェック通過後

1. `jj safe-push` コマンド（未導入時は `jj git push`）で安全に push
   - diverge チェック
   - dry-run 確認
2. `/issue-driven-flow:open-pr` で PR 作成
   - Issue 番号を `Closes #NNN` として自動挿入
   - タイトルは Conventional Commits 形式

## 局面 6a: コードレビュー（自分がレビュアー）

**トリガー**: レビューを依頼された時

1. `/issue-driven-flow:review` でチェックリストに沿ってレビュー
2. `pr-review-format` スキルで正しい suggestion ブロック形式でコメント
3. inline suggestion 形式（` ```suggestion ` ）を使う

## 局面 6b: レビュー返信（自分が実装者）

**トリガー**: レビューコメントが届いた時

1. `/issue-driven-flow:respond` で未返信スレッドを自動分類
   - `valid-fix`: 自動修正 + 返信
   - `invalid-reject`: 却下返信のみ
   - `needs-human`: スキップ（手動対応）
2. `--dry-run` で実行予定を先に確認可能
3. push は `jj safe-push` 経由で安全に実施

## 局面 7: マージ後の後始末

**トリガー**: PR がマージされた後

1. `/issue-driven-flow:finish-feature` で一括クリーンアップ
   - PR マージ確認
   - Issue クローズ確認
   - jj workspace / git worktree 削除
   - 次の Issue 提案

## クロスカット関心事

### トークン削減 (RTK)
- すべての `gh` / `git` コマンドは `rtk gh` / `rtk git` を使う
- `context-generation` スキルの RTK パターンを参照

### セキュリティ
- Write/Edit 時に `security-scan.sh` が自動実行
- `app-security` / `package-security` スキルを参照

### 並列開発
- 複数 Issue を並行するなら `jj workspace add` で workspace を分ける
- `jj-vcs-workflow` スキルの `workspace.md` ガイドを参照

### セッション間引き継ぎ
- `context-keeper` スキルで `.claude/session-summary.md` が自動生成される
- セッション開始時に前回サマリが自動注入される

### 新しい統括 (Coordinator) SubAgent を作るとき
- 複数の局面（複数の Skill / SubAgent）を合成する新しいドメインのワークフローを統括させたい場合は、
  L1 統括 SubAgent を新規作成する
- コピー用テンプレート: `agents/templates/coordinator-template.md`
  - フロントマター（`name` / `description` / `tools` / `skills` / `model`）と本文（`Step n:` 目的のみ・
    成功条件・失敗時フォールバック）の雛形をプレースホルダー付きで提供する
  - 使い方: `agents/<domain>-coordinator.md` にコピーし、`<...>` を実値へ置換、先頭のコメントを削除する
  - トリガーワードは coordinator のルーティング表と同期させること
