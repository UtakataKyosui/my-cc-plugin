---
name: overlap-policy
description: >
  Skill/SubAgent/Command の役割重複判定ルール集。overlap-classifier Agent がクラスタを
  keep/drop/coexist に分類する際の基準として参照する。
---

# Overlap Policy（役割重複判定ルール）

## 判定の優先順位

以下の順に評価し、最初に一致したルールを適用する。

### 1. Builtin と重複 → カスタム側を drop 強推奨

Claude Code 組み込みの `/review`, `/init`, `/security-review`, `/loop`, `/schedule` 等と
**同名またはほぼ同一の目的**を持つカスタム Skill/Command が存在する場合、カスタム側を drop 推奨。

- 理由: 組み込みは将来的に維持・改善され、全ユーザーに提供される。カスタム実装は管理コストのみ増やす。
- 例外: 組み込みを**拡張・特化**している場合（例: zenn 記事専用レビュー）は coexist でよい。
  ただし description に「Extends builtin /review for ...」のような明示を推奨。

### 2. 外部マーケットプレイス由来 vs ローカル重複 → ローカル側を drop 推奨

同一機能が `source: marketplace` と `source: repo` の両方に存在する場合、
repo 側（ローカルカスタム）を drop 推奨。

- 理由: マーケットプレイス版は独立した保守体制を持つ。ローカル版の独自性がなければ管理コストが高い。
- 例外: ローカル版がマーケットプレイス版にない機能（C2Lab 固有の CI 統合等）を持つ場合は coexist。

### 3. 言語/ドメインが異なれば coexist

同じ役割カテゴリでも対象ドメイン・言語・フレームワークが異なる場合は共存を許容する。

- OK 例: `rust/agents/code-reviewer.md`（Rust コード専用）vs `code-review/agents/code-reviewer.md`（汎用）
  → 汎用は keep、言語特化は coexist（ただし「汎用 code-reviewer を呼び出してから特化知識を適用」
  のように統合できるなら統合を検討）
- NG 例: `jj-vcs-workflow/skills/jj-vcs-workflow` と `harness-toolkit/skills/vcs-jj`
  → 同一ツール（jj）で説明内容が重複する → どちらか一方に統合を推奨

### 4. グローバル個人ツール → 参考表示のみ

`source: user-global`（`~/.claude/` 配下）のアセットは個人専用環境にのみ存在するため、
クラスタに含めて表示するが drop 推奨は出さない（個人の判断に委ねる）。

ただし `source: repo` や `source: marketplace` と **完全同名** の場合は、
個人版を使い続ける価値があるかを確認するよう注記する。

### 5. Description 類似度が高い → drop 推奨

同カテゴリ内で description の Jaccard 類似度 ≥ 0.70、またはほぼ同じ文章の場合は
「一方は不要な可能性が高い」として drop 推奨。

## カテゴリ分類マップ

| category_hint | 含まれるキーワード（いずれか） |
|---|---|
| pr-review | review, pull request, pr, code review, レビュー |
| vcs | jj, jujutsu, vcs, version control, git, branch, commit, push |
| screenshot | screenshot, スクリーンショット, capture, playwright |
| testing | tdd, test, coverage, spec, テスト |
| package-manager | pnpm, npm, yarn, bun, uv, pip, cargo install |
| automation | loop, schedule, cron, interval, recurring, 自動 |
| security | security, vulnerability, semgrep, cve, ghasec |
| project-setup | init, initialize, scaffold, setup, CLAUDE.md |
| code-quality | lint, format, refactor, simplify, clean |
| plugin-dev | plugin, skill, hook, agent, command, mcp |
| meta | config, settings, permission, keybinding, help |

## Issue 起票ルール

- **cluster_id** はカテゴリ + シリアル番号（例: `pr-review-001`）
- タイトル: `[overlap-audit] <category>: <name1> / <name2> / ...`
- ラベル: `audit/overlap`, `auto-generated`
- 冪等性: `~/.cache/overlap-audit/posted.json` に記録した cluster_id をチェックし、起票済みはスキップ。GitHub 上の既存 Issue との照合は行わない（`--force` で再起票可能）
- 1 回の `/audit-overlap` 実行で起票する Issue は最大 20 件（多すぎる場合は `--limit=N` で制御）

## "keep" 選定の基準

複数の候補がある場合、以下の順に優先する:

1. builtin（ビルトイン組み込み）> marketplace > repo > user-global
2. description が詳細で文脈情報が多い方
3. より広いスコープ（言語特化 < 汎用）を持つ方
4. 最後に更新されたファイル（新しい方）
