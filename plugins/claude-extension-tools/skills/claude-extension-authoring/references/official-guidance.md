# 公式ガイダンス

作成・レビュー時は、対象となる公式ドキュメントを必要な範囲だけ参照する。本文へ仕様を複製せず、リンク先の更新を優先する。

## Claude Code

- [Hooks](https://code.claude.com/docs/ja/hooks.md): Hookイベント、matcher、command/prompt/agentの使い分け、JSON入出力。
- [Plugins reference](https://code.claude.com/docs/ja/plugins-reference.md): Pluginマニフェスト、コンポーネント配置、検証。
- [Subagents](https://code.claude.com/docs/ja/sub-agents.md): frontmatter、ツール制限、権限、Skillのプリロード、独立コンテキスト。
- [Skills](https://code.claude.com/docs/ja/skills.md): descriptionによる選択、`SKILL.md`、参照資料、scripts、invocation policy。
- [Plugins](https://code.claude.com/docs/ja/plugins.md): 配布可能なSkill、Subagent、Hook、MCPの構成と名前空間。
- [Memory and Rules](https://code.claude.com/docs/ja/memory.md#organize-rules-with-claude/rules/): `.claude/rules/`、`paths`によるスコープ、RulesとSkillの使い分け。
- [Best practices](https://code.claude.com/docs/ja/best-practices.md): コンテキスト管理、計画、検証、作業を小さく保つ方法。

## Prompting and evaluation

- [Prompting Claude Sonnet 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5.md): effort、ツール利用、明示的な指示、出力の調整。
- [Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5.md): 長時間作業、委譲、自己修正、スコープ管理。
- [Prompting Claude Fable 5.1](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-1.md): 進捗、ツール呼び出し、対象範囲、検証、コンパクション。
- [Prompting best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices.md): 明確な指示、例、XML構造、長文コンテキスト、Agenticワークフロー。
- [Reduce hallucinations](https://platform.claude.com/docs/ja/test-and-evaluate/strengthen-guardrails/reduce-hallucinations.md): 不確実性の許可、引用、根拠による検証。
- [Develop tests](https://platform.claude.com/docs/ja/test-and-evaluate/develop-tests.md): 期待する動作をテストにし、代表例と失敗例で評価する方法。

リンク先のモデル名やURLが変更された場合は、レビュー時に現在の公式ページへ追従し、古いモデル固有の指示を一般化しない。
