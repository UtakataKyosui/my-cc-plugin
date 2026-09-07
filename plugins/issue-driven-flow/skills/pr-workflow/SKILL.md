---
name: pr-workflow
description: >
  PR ワークフロー全体（CI 検証 → PR 作成 → レビュー → 返信 → マージ）の 5 段階を標準化したアンブレラスキル。
  以下の場合に使用: (1) PR を作成するとき (2) push 前に CI を検証したいとき (3) マージ前の準備確認をするとき
  (4) 「PR を作る」「CI チェック」「push する前に」「マージ準備」「pre-push」と指示されたとき
  (5) PR レビューコメントに返信するときの全体フローを把握したいとき
  詳細な返信フォーマットは `auto-pr-responder` skill、レビュー投稿の formatは `pr-review-format` skill を参照する。
---

# PR ワークフロー（5 段階フロー）

PR 作成から CI 検証・レビュー対応・マージまでの一連の手順。

## ライフサイクル概要

```
1. ブランチ作成 → 2. 実装 → 3. CI ローカル検証 → 4. PR 作成 → 5. レビュー対応 → 6. マージ
```

## Phase 1: CI ローカル検証（push 前に必ず実施）

push する前に、変更したファイルに対応する CI コマンドをすべて実行する。
詳細なコマンドは `references/ci-checks.md` を参照。

**検出方法**: プロジェクトルートのファイルで言語を判定する。

| ファイル | 言語 | 実行すべき CI |
|---------|------|--------------|
| `package.json` | TypeScript/JS | prettier + eslint |
| `pyproject.toml` / `setup.py` | Python | ruff check + ruff format |
| `Cargo.toml` | Rust | cargo fmt --check + cargo clippy |

コマンド: `/pr-workflow:ci-check [--fix]`

**重要**: 1 つの CI を直して push し、別の CI が落ちるのを繰り返さない。
push 前に全種類の CI を一度に確認する。

## Phase 2: PR 作成

PR を作成するときの規約は `references/conventions.md` を参照。

**要点**:
- タイトル: `<type>: <概要>` 形式（feat, fix, refactor, docs, chore）
- 本文: 変更の目的（why）を記載する
- Issue 対応 PR には必ず `Closes #nnn` を含める
- jj を使う場合: `jj safe-push` コマンド（alias、未導入時は `jj git push`）を使う

コマンド: `/pr-workflow:open-pr <title>`

## Phase 3: レビュー（自分が他者をレビューする側）

他者の PR をレビューする場合は、以下のコマンドを使う:

- `/pr-workflow:review-principle` — レビュー原則の確認
- `/pr-workflow:review-checklist` — チェックリスト適用

レビュー投稿のフォーマットは `pr-review-format` skill を必ず使う:
- top-level body に「適正な実装」「修正することが望ましいところ」の両セクションを含める
- 個別の指摘は ` ```suggestion ` ブロック付きインラインコメントとして投稿
- pr-workflow-code-reviewer エージェント経由でも可

## Phase 4: コメント返信（自分が PR を出している側）

PR レビューコメントへの返信は **2 系統** ある:

- `/pr-workflow:respond [PR#]` — pr-triage エージェントで自動 3 分類し、inline suggestion で返信
  - `--dry-run` で実行予定を PR コメントに出力できる
- `/pr-workflow:respond-manual [PR#]` — 各スレッドを手動確認しながら対応

詳細な triage 規範・返信フォーマット・失敗モードは `auto-pr-responder` skill を参照。

**規約**:
- コード提案には必ず ` ```suggestion` ブロックを使う（plain コメントは不可）
- 各コメントに返信してから resolve する
- 他レビュワーのコメントスレッドには返信しない

## Phase 5: マージ前チェックリスト

マージする前に以下を確認する:

- [ ] すべての CI が green
- [ ] すべてのレビューコメントに返信済み（resolved かどうかではなく replied かどうか）
- [ ] 不要なデバッグコード・console.log がない
- [ ] 関連するテストが追加・更新されている

詳細リファレンスは `references/ci-checks.md` / `references/conventions.md` を参照。
