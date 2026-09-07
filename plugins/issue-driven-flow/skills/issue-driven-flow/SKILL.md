---
name: issue-driven-flow
description: >
  Issue-Driven 開発の 0 → 1 全フローをオーケストレーションするメインスキル。
  コマンドの使い方・フロー図・各局面のトリガー条件を提供する。
  「今何をすればいいか迷ったとき」に参照する。
---

# issue-driven-flow — 0 → 1 開発フローガイド

このプラグインは **Issue を起点に開発し、PR マージまで一本のフローで完結させる** ための統合プラグイン。

## フロー全体図

```
[0. プロジェクト初期化]   /issue-driven-flow:init-project
        ↓
[1. Issue 選定・着手]     /issue-driven-flow:start-feature
        ↓
[2. 実装]                 (jj safe-new で Change を刻む)
        ↓
[3. コミット整備]          /issue-driven-flow:commit-change
        ↓
[4. CI チェック]           /issue-driven-flow:ci-check
        ↓
[5. PR 作成]              /issue-driven-flow:open-pr
        ↓
[6a. コードレビュー]       /issue-driven-flow:review  (自分がレビュアーの場合)
[6b. レビュー返信]         /issue-driven-flow:respond (自分が実装者の場合)
        ↓
[7. マージ・後始末]        /issue-driven-flow:finish-feature
```

いつでも現状確認: `/issue-driven-flow:status`

## コマンド一覧

| コマンド | 局面 | 説明 |
|---|---|---|
| `/issue-driven-flow:init-project` | 0 | リポジトリ初期化（初回のみ） |
| `/issue-driven-flow:start-feature` | 1 | Issue 選定 → ブランチ → workspace 作成 |
| `/issue-driven-flow:commit-change` | 3 | Conventional Commits メッセージを起案・設定 |
| `/issue-driven-flow:ci-check` | 4 | ローカル lint / test / type-check |
| `/issue-driven-flow:open-pr` | 5 | PR 作成（Issue 番号自動挿入） |
| `/issue-driven-flow:review` | 6a | コードレビュー（チェックリストに沿って） |
| `/issue-driven-flow:respond` | 6b | レビューコメントへ自動分類・修正・返信 |
| `/issue-driven-flow:finish-feature` | 7 | マージ後クリーンアップ + 次タスク提案 |
| `/issue-driven-flow:status` | いつでも | jj/Issue/PR/CI 状況ダッシュボード |

## コンポーネント

| カテゴリ | スキル名 |
|---|---|
| VCS (jj) | `jj-vcs-workflow`, `context-keeper` |
| Issue 管理 | `my-task`, `task-start` |
| PR フロー | `pr-workflow`, `auto-pr-responder`, `pr-review-format` |
| コード探索 | `code-exploration`, `context-generation` |
| 並列実行 | `parallel-execution` |
| 依存管理 | `dependency-management` |
| ブランチ整理 | `branch-cleanup` |
| GitHub CLI | `gh` |
| コミット規約 | `conventional-commits` |

## 前提ツール（必須）

| ツール | インストール |
|---|---|
| `jj` (Jujutsu) | `cargo install jj-cli` または `brew install jj` |
| `gh` (GitHub CLI) | `brew install gh` |
| `lefthook` | `brew install lefthook` |
| `rtk` (Rust Token Killer) | `cargo install rtk` |

## 前提ツール（推奨）

| ツール | 用途 |
|---|---|
| `fd` | 高速ファイル探索 |
| `ripgrep` (rg) | 高速検索 |
| `repomix` | コンテキスト生成 |
| `gh extension install seachicken/gh-poi` | マージ済みブランチ掃除 |
| `gh extension install UtakataKyosui/gh-my-task` | Issue/PR 一覧管理 |

## 既存プラグインとの共存

このプラグインは以下のプラグインを **物理コピーで統合** している。
同時に有効化するとフック・スキルが二重発火する恐れがある。

**推奨: `issue-driven-flow` を使う場合は以下を無効化する**

- `vcs-workflow`
- `pr-workflow`
- `gh-my-task`
- `branch-cleanup`
- `harness-toolkit`
- `gh`

個別プラグインを引き続き使いたい場合は `issue-driven-flow` を外す。
