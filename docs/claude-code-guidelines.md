# Claude Code拡張の実装指針

このMarketplaceはClaude Code公式ドキュメントの次の原則に合わせる。

- [一般的なワークフロー](https://code.claude.com/docs/ja/common-workflows): 探索、計画、実装、検証を分け、調査は必要に応じてSubagentへ委譲する。
- [ベストプラクティス](https://code.claude.com/docs/ja/best-practices): コンテキストを小さく保ち、目的・制約・検証方法をプロンプトとSkillに明記する。
- [Skills](https://code.claude.com/docs/ja/skills): frontmatterの`description`を起動条件として具体的に書き、長い資料は参照ファイルへ分離する。
- [Subagents](https://code.claude.com/docs/ja/sub-agents): 独立した作業は専用エージェントへ分け、`tools`、`disallowedTools`、`permissionMode`、`maxTurns`で権限と実行範囲を明示する。
- [Hooks](https://code.claude.com/docs/ja/hooks-guide): 常に同じ判定になる処理はcommand hookとスクリプトにし、判断が必要な処理だけをpromptまたはagent hookにする。
- [Plugins](https://code.claude.com/docs/ja/plugins): 共有・再利用・バージョン管理が必要な機能をPluginとして配布し、Plugin内のコマンドやSkillは名前空間を持たせる。
- [Prompt caching](https://code.claude.com/docs/ja/prompt-caching): 毎回読む大きな説明をfrontmatterへ詰め込まず、必要なときだけ参照資料を読む構成にする。

## 実装チェック

新しいSkill、Command、Subagent、Hookを追加するときは次を確認する。

1. YAML frontmatterに、用途・起動条件・引数・権限を記載する。
2. 本文には実行手順、入力、出力、失敗時の扱い、検証方法を書く。
3. 繰り返し使う判定や外部コマンドは、テスト可能なスクリプトへ切り出す。
4. 外部状態を変更する処理は自動委譲を無効にし、明示的な確認を要求する。
5. 長いリファレンスは`references/`や`docs/`へ分け、Skill本文からリンクする。
6. `claude plugin validate`と`python3 scripts/validate_marketplace.py`を実行する。
