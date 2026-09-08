---
name: claude-extension-authoring
description: Claude CodeのSkill、Subagent、Rules、Hooks、Pluginを公式仕様に沿って設計・作成・更新する。新規作成、frontmatter設計、権限設定、参照資料の分割、検証方法の相談で使用する。
argument-hint: "<artifact path> [skill|subagent|rule|hook|plugin]"
user-invocable: true
---

# Claude Code拡張の作成

Claude Codeの拡張を作成・更新する。対象を決める前に既存ファイル、呼び出し元、実行権限、検証方法を確認する。

## 対象の選び方

| 対象 | 使う場合 | 成果物 |
| --- | --- | --- |
| Skill | 再利用する知識や複数手順を、必要なときだけ読み込ませる | `<name>/SKILL.md`と必要な`references/`、`scripts/` |
| Subagent | 独立した文脈、専用ツール、別の権限で作業させる | `agents/<name>.md` |
| Rule | 常に適用する事実や対象パス固有の制約を読み込ませる | `.claude/rules/<name>.md` |
| Hook | 毎回同じ判定を確実に実行する | `hooks/hooks.json`と実行スクリプト |
| Plugin | 複数プロジェクトへ配布し、名前空間とバージョンを管理する | `.claude-plugin/plugin.json`と配下の拡張 |

判断が必要な処理をHookのShell条件だけで表現せず、決定的な処理をHookとスクリプトへ切り出す。長い手順や条件別の資料をSkill本文へ詰め込まず、参照資料へ分けて必要なときだけ読む。

## 作成手順

1. 対象の配置、既存のfrontmatter、呼び出し元、関連するHookを調べる。
2. 目的、起動条件、対象外、入力、成果物、失敗時の扱いを1段落で定義する。
3. frontmatterを作る。Skillは`name`と`description`、Subagentは`name`、`description`、`model`、`tools`、必要なら`disallowedTools`、`permissionMode`、`skills`、`maxTurns`を明示する。
4. 本文には、実行順序が必要な場合だけ番号付きの手順を使い、判断基準と検証方法を具体的に書く。
5. 長い仕様、例、モデル固有の注意は`references/`へ移し、本文から読む条件をリンクする。
6. 繰り返す変換、検査、外部CLI操作は`scripts/`へ実装し、正常系・失敗系をテストする。
7. `python3 scripts/validate_extension.py <path>`で構造を検証する。
8. `claude-extension-reviewer`へ実際の利用例と変更対象を渡し、作成物を独立レビューする。

## Frontmatterの要点

Skillの`description`は、Claudeが選択できる短い起動条件にする。細かい手順や全機能一覧をdescriptionへ列挙しない。ユーザーの明示呼び出しだけに限定する副作用のあるSkillには`disable-model-invocation: true`を設定する。

Subagentは最小権限にする。読み取り専用レビューでは`Write`、`Edit`、`Bash`を`disallowedTools`へ入れ、計画・調査用途では`permissionMode: plan`を使う。作成Skillを利用するレビューSubagentはfrontmatterの`skills`に`claude-extension-authoring`を指定する。

Rulesは事実や不変条件を短く書き、対象パスが限定される場合はfrontmatterの`paths`でスコープを限定する。手順や作業のレシピはRulesではなくSkillに置く。

## 品質ゲート

- 仕様にない機能、権限、ファイルを追加していない。
- Skillのdescriptionが他のSkillと区別でき、無関係な依頼を誘発しない。
- 参照資料は本文から辿れ、同じ説明を複数ファイルへ重複させていない。
- 外部状態を変更する処理は、明示確認または明示的なユーザー呼び出しを要求する。
- 不確かな事実は推測せず、根拠、未確認事項、再現手順を残す。
- 実際のサンプル入力で、期待するファイルと出力が得られる。

詳細な仕様と公式リンクは[references/official-guidance.md](references/official-guidance.md)を参照する。構造検証は`../../../scripts/validate_extension.py`を実行する。
