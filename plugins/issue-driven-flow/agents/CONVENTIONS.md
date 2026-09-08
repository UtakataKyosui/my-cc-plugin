# agents/ 命名・責務規約とロール分類

このドキュメントは `issue-driven-flow` プラグインの `agents/` 配下に存在する各 SubAgent を
ロール階層（taxonomy）に分類し、命名・責務の規約を定義する。新しい agent を追加・変更するときは
本ドキュメントの規約に従う。

> 上位の設計規約（プラグイン横断）は `~/.claude/rules/agent-skill-architecture.md` に対応する。
> 本ドキュメントはそのプラグイン内ローカル版であり、`agents/` 配下の実態に基づいて記述する。

## ロール taxonomy と判定基準

agent を以下の 3 階層に分類する。判定は **宣言された `tools` / `skills` / `description` の実態** に基づく。

### L1 統括 (coordinator)

複数の agent を調整・委譲してドメインのワークフローを統括する agent。

判定基準（いずれかを満たす）:

- `skills:` フロントマターで能力 Skill をプリロードしている
- `tools` に `Skill` または `Agent` を含む（他 Skill を合成、または他 agent を生成する）
- `description` が「複数 agent を調整・委譲する」責務を明示している

### L2 worker

実装・修正・成果物生成を行う単一責務の agent。

判定基準（すべてを満たす）:

- `tools` に `Agent` を **含まない**（他 agent を生成しない）
- `tools` に `Skill` を **含まない**（他 Skill を合成しない）
- `tools` に `Edit` / `Write` / `Bash` のいずれかを含み、ファイルや成果物を **生成・変更する**

### L2 調査役 (research)

読み取り専用で情報収集・分析・レポートを行う agent。新しいコードファイルを生成しない。

判定基準（すべてを満たす）:

- `tools` が `Read` / `Grep` / `Glob` の範囲に収まる（`Edit` / `Write` でソースを書き換えない）
- ソースコードや設定ファイルを **生成・変更しない**（分析レポート・分類結果の出力に限定）

> 補足: `tdd-compliance-checker` / `tool-recommender` のように `Bash` を持つが、その用途が
> 「言語検出・ツール存在確認・分岐カウントなどの読み取り系コマンド」に限定され、ソースを変更しない agent も、
> 責務の実態は調査役（research）である。本ドキュメントでは「ソースを変更しない読み取り・分析専用」を
> 調査役の本質的判定基準とし、`Bash` の有無は二次的に扱う。各行の rationale でその根拠を明示する。

## 分類テーブル

`agents/` には実ファイル **8 個** が存在する。各 agent を上記の判定基準で分類した結果を示す。

| ファイル名 | 宣言 `name` | `tools` | `skills:` | layer | 分類根拠（実態） |
|---|---|---|---|---|---|
| `code-reviewer.md` | `pr-workflow-code-reviewer` | Read, Edit, Write, Glob, Grep | なし | **L2 worker** | `description` が「修正点があれば実装する」と明示。`Edit`/`Write` でコードを書き換える単一責務。`Agent`/`Skill` なし。 |
| `harness-setup.md` | `harness-setup` | Read, Glob, Grep, Bash | なし | **L2 worker** | OS/パッケージマネージャ検出・ツール存在確認を `Bash` で行い、インストール手順を案内する。環境セットアップの実務を担う単一責務。`Agent`/`Skill` なし。 |
| `pr-triage.md` | `pr-triage` | Read, Grep, Glob | なし | **L2 調査役 (research)** | `tools` が `Read`/`Grep`/`Glob` のみ。`description` が「コード修正は行わず、分類のみを責務とする」と明示。未返信スレッドを 3 分類し JSON を出力するだけで、ソースを変更しない。 |
| `review-fixer.md` | `review-fixer` | Read, Edit, Write, Glob, Grep | なし | **L2 worker** | レビューコメントに基づき `Edit`/`Write` でコードを修正する単一責務。`Agent`/`Skill` なし。 |
| `tdd-compliance-checker.md` | `tdd-compliance-checker` | Read, Glob, Grep, Bash | なし | **L2 調査役 (research)** | `description`/本文が「自動修正は行わない。レポートと提案のみ」と明示。`Bash` を持つが用途は言語検出・分岐カウント等の読み取り系で、ソースを変更しない。実態は調査・レポート。 |
| `tool-recommender.md` | `rust-cli-tool-recommender` | Read, Glob, Grep, Bash | なし | **L2 調査役 (research)** | クラシック Unix コマンドの Rust 代替を提案するのみ。`Bash` は `command -v` 等のチェック用途で、ソースを変更しない。`Edit`/`Write` なし。実態は助言・分析。 |

### 階層サマリー

| layer | 件数 | 該当 agent |
|---|---|---|
| L1 統括 (coordinator) | 0 | （なし） |
| L2 worker | 3 | code-reviewer, harness-setup, review-fixer |
| L2 調査役 (research) | 4 | pr-triage, tdd-compliance-checker, tdd-test-reviewer, tool-recommender |

**注記**: 本プラグインの `agents/` には L1 統括 (coordinator) が存在しない。
`tools` に `Skill`/`Agent` を含む agent も `skills:` プリロードを持つ agent も 1 つもない。
PR レビューの全体オーケストレーションは（プラグイン外の）コマンド層・スキル層が担っており、
`pr-triage`（分類）と `review-fixer`（修正）は親コマンドから委譲される L2 部品として設計されている。

## ファイル名 ↔ 宣言 name の不整合と実体の照合

### ファイル名と宣言 `name` が異なる agent（2 件）

Issue は `pr-workflow-code-reviewer` / `rust-cli-tool-recommender` という名前を挙げているが、
これらはファイル名ではなく **agent ファイル内部で宣言された `name`** である。実態は以下のとおり。

| ファイル名 | 宣言 `name`（フロントマター） |
|---|---|
| `code-reviewer.md` | `pr-workflow-code-reviewer` |
| `tool-recommender.md` | `rust-cli-tool-recommender` |

残り 5 個（harness-setup, pr-triage, review-fixer, tdd-compliance-checker,
tdd-test-reviewer）はファイル名と宣言 `name` が一致している。

### 実ファイルの照合

- `change-planner` と `conventional-commit-writer` は本プラグインへ統合した。
- `issue-driven-flow` の `agents/` には、ここに記載するローカルAgentだけを置く。

## 命名・責務規約

新しい agent を追加するときは以下に従う。

### 命名規約

- **ファイル名 = 宣言 `name`** を原則とする（kebab-case）。両者を一致させることで、
  ファイルシステム上の探索と、agent 呼び出し時の `name` 解決が一意になる。
- **L1 統括 (coordinator)**: `<domain>-coordinator` サフィックスを付ける
  （例: `pr-review-coordinator`、`team-coordinator`）。
- **L2 worker**: 「動詞 + 対象」または「対象 + 役割名詞」で責務が一目で分かる名前にする
  （例: `review-fixer`、`harness-setup`）。
- **L2 調査役 (research)**: 「対象 + checker / triage / recommender」など
  「調査・分類・提案」を表す名詞で終える（例: `tdd-compliance-checker`、`pr-triage`）。

### 責務規約

- 1 つの agent は **単一責務** に絞る。複数ドメインのワークフローを束ねる場合は L1 統括として切り出す。
- **調査役 (research)** は `Edit`/`Write` を `tools` から外し、読み取り専用に保つ。
  分析・分類・提案のみを行い、ソースの変更は worker に委譲する。
- **worker** は他 agent を生成しない（`tools` に `Agent` を含めない）。
- **統括 (coordinator)** のみが `skills:` プリロードと `tools` の `Skill`/`Agent` を使う。
- フロントマターには `name` と `description` を必ず含める（バリデーション必須項目）。

### 改名候補（フォローアップで別 Issue 化）

本ドキュメントでは **改名を一切行わない**。以下はフォローアップとして別 Issue で扱う候補のみを記録する。

| 対象ファイル | 現状 | 規約上の問題 | 推奨方針（別 Issue で検討） |
|---|---|---|---|
| `code-reviewer.md` | ファイル名 `code-reviewer` ≠ 宣言 `name: pr-workflow-code-reviewer` | ファイル名と宣言 name が不一致 | ファイル名を `pr-workflow-code-reviewer.md` に揃えるか、宣言 name を `code-reviewer` に揃える。参照箇所（コマンド・スキル）への影響調査が必要。 |
| `tool-recommender.md` | ファイル名 `tool-recommender` ≠ 宣言 `name: rust-cli-tool-recommender` | ファイル名と宣言 name が不一致 | ファイル名を `rust-cli-tool-recommender.md` に揃えるか、宣言 name を `tool-recommender` に揃える。同上の影響調査が必要。 |

> 上記 2 件は機能上の不具合ではないが、命名規約「ファイル名 = 宣言 name」に反する。
> 改名は参照先（plugin.json の auto-detection、コマンド/スキルからの呼び出し名）への影響を伴うため、
> 本 Issue のスコープ外とし、別 Issue で安全に対応する。
