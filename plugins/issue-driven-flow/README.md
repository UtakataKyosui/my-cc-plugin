# issue-driven-flow

**これさえあれば GitHub Issue から PR マージまで回る**、jj標準のオールインワン開発フロープラグイン。TDDでは、実装前に別エージェントがテスト計画を審査し、PASSになるまで実装を開始しない。

`vcs-workflow` / `pr-workflow` / `gh-my-task` / `branch-cleanup` / `harness-toolkit` / `gh` を統合し、1 つのプラグインで完結させる。

---

## フロー

```
/init-project     → /start-feature → テスト設計・審査 → (実装) → /commit-change
                                                    ↓
/finish-feature ← /respond ← /open-pr ← /ci-check
```

いつでも現状確認: `/issue-driven-flow:status`

---

## コマンド

| コマンド | 説明 |
|---|---|
| `/issue-driven-flow:init-project` | jj・Lefthook・RTK を一括セットアップ（初回のみ） |
| `/issue-driven-flow:start-feature` | Issue 選定 → ブランチ → workspace → Change 計画 |
| `/issue-driven-flow:commit-change` | Conventional Commits + Issue 番号をエージェントが起案 |
| `/issue-driven-flow:ci-check` | push 前のローカル lint / test / type-check |
| `/issue-driven-flow:open-pr` | PR 作成（`Closes #NNN` 自動挿入） |
| `/issue-driven-flow:review` | コードレビュー（チェックリスト形式） |
| `/issue-driven-flow:respond` | レビューコメントを自動分類・修正・返信 |
| `/issue-driven-flow:finish-feature` | マージ後クリーンアップ + 次タスク提案 |
| `/issue-driven-flow:status` | jj / Issue / PR / CI ダッシュボード |
| `/issue-driven-flow:tdd-init` | TDD 環境初期化（言語検出・フレームワーク提案） |
| `/issue-driven-flow:tdd-cycle` | Red-Green-Refactor サイクルのフルガイド実行 |
| `/issue-driven-flow:tdd-suggest-framework` | 言語別テストフレームワーク提案 |

---

## 必須ツール

```bash
brew install jj gh lefthook
cargo install rtk  # または別途 RTK インストール手順を参照
```

## 推奨ツール

```bash
brew install fd ripgrep
cargo install repomix
gh extension install seachicken/gh-poi
gh extension install UtakataKyosui/gh-my-task
```

## jj を使う場合の依存（任意）: jj-exec-aliases

`jj safe-new`（Change 境界の安全な移動）/ `jj safe-push`（意図しない force-push の防止）は、
外部ツール [jj-exec-aliases](https://github.com/UtakataKyosui/jj-exec-aliases) が提供する。
本プラグインは jj safe-* の実体（スクリプト・alias・ブロック hook）を **一切持たない**ため、
jj でこのフローを使う場合は jj-exec-aliases を別途導入する（同リポジトリの手順に従う）。

未導入でもプラグインは動作する。`scripts/push.py` は jj を素の `jj git push`（確認後 push）に
フォールバックし、各 SKILL / コマンドの `jj safe-*` 案内は jj-exec-aliases 導入時に有効になる。

---

## セットアップ

### 1. プラグインのインストール

`claude.ai/code` のプラグイン設定から `utakata-plugins` マーケットプレイスで `issue-driven-flow` を追加する。

### 2. プロジェクトの初期化

既存リポジトリで `/issue-driven-flow:init-project` を実行する。自動で以下が行われる:

- `jj git init --colocate`（jj と git を共存）
- `lefthook.yml` の展開とインストール
- `.claude/jj-scope.json` の初期化
- `.github/ISSUE_TEMPLATE/task.md` の作成

---

## Conventional Commits + Issue 番号の強制

ブランチ名 `feat/123-auth` から Issue 番号を自動抽出し、`(#123)` を補完する。

Lefthook が以下の形式を強制する:

```
feat(auth): ログイン機能を追加する (#123)
```

一時スキップ（初期コミット等）: `SKIP=commit-msg lefthook run commit-msg`

---

## 統合済みプラグイン

このプラグインにはPRレビューに必要なスクリプトとSkillを同梱している。配布時の正本はこのリポジトリ内のファイルであり、別Marketplaceから自動同期しない。

| コンポーネント | 配置 | 内容 |
|---|---|---|
| `pr-review-toolkit` | `scripts/`、`skills/pr-review-toolkit/` | PRの取得、差分分析、レビュー対応 |

### `pr-review-toolkit` のスクリプト役割

PR レビュー時に PR 内容（diff・ファイル変更・コメント）を構造化取得・分析する stdlib のみの Python スクリプト群。`skills/pr-review-toolkit/SKILL.md` が `${CLAUDE_PLUGIN_ROOT}/scripts/` から直接呼び出す。

| スクリプト | 役割 |
|---|---|
| `fetch_pr.py` | PR メタ情報 + diff + ファイル一覧を 1 つの構造化 JSON で取得（`--include-comments` / `--no-diff`） |
| `parse_diff.py` | `fetch_pr.py` の diff を hunk / 行単位の構造化 JSON にパース（stdin パイプ受け） |
| `analyze_pr.py` | `fetch_pr.py` の出力から統計・言語分布・大規模変更・依存変更・秘密情報警告を抽出 |
| `pr_common.py` | 上記が共有する gh CLI ヘルパー（PR 参照パース・repo 検出・`run_gh`）。`fetch_pr.py` が兄弟 import |

典型フロー: `python3 scripts/fetch_pr.py <PR#> | python3 scripts/analyze_pr.py`

### レビュー対応スクリプトの役割パイプライン

既存の `review_fetcher.py` / `triage_input_builder.py` とは責務が異なり、衝突しない（ファイル名も重複なし）。レビュー *対応*（返信）系のパイプラインは以下:

```
fetch_pr.py            構造化された PR メタ + diff 取得（レビュー閲覧・分析向け）
  ↓
triage_input_builder.py  未返信スレッドを pr-triage 用に整形（auto-pr-responder）
  ↓
pr-triage agent          valid-fix / invalid-reject / needs-human に分類
  ↓
post_reply.py            分類結果を inline threaded reply として投稿
```

`analyze_pr.py` の秘密情報検知（`credential_pattern` 等の `warnings`）はレビュー時の参考情報であり、`hooks/scripts/security-scan.sh` フックとは独立した別レイヤー（フックは変更しない）。

## 既存プラグインとの共存について

統合済みプラグインを同時に有効化するとフックが二重発火する。

**`issue-driven-flow` を使う場合は以下を無効化することを推奨:**

- `tdd-enforce`
- `vcs-workflow` / `jj-vcs-workflow`
- `pr-workflow` / `code-review` / `auto-pr-responder` / `pr-lifecycle`
- `pr-review-toolkit`
- `gh-my-task`
- `branch-cleanup`
- `harness-toolkit`
- `gh`

個別プラグインを引き続き使いたい場合は `issue-driven-flow` を入れない。

---

## 依存関係と更新方針

このMarketplaceで配布するPluginの正本は、このリポジトリの各 `plugins/<name>` 配下にある。過去の上流Plugin名や手動同期手順は配布上の依存ではない。外部ツールに依存する場合だけREADMEと [`docs/plugin-architecture.md`](../../docs/plugin-architecture.md) に明記し、更新時は対応するPluginのバージョンを上げる。

---

## ライセンス

MIT
