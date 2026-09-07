---
name: context-keeper
description: This skill should be used when the user wants to "セッション間でコンテキストを引き継ぐ", "コンテキスト圧縮前に重要情報を保護する", "git/jj の変更状態を Claude に自動で把握させる", or "前回セッションの申し送りを確認する". Also activates when the user asks about ".compaction-notes.md の書き方", "session-summary.md", or "context-keeper の設定".
version: 0.1.0
---

# context-keeper スキル

context-keeper プラグインは 4 つのフックで動作するコンテキスト保護・継承プラグインです。

## 機能概要

| フック | 機能 | 無効化環境変数 |
|---|---|---|
| `UserPromptSubmit` | git/jj の変更ファイル・ブランチをプロンプト送信時に自動注入 | `CONTEXT_KEEPER_DISABLE_GIT_INJECT=1` |
| `PreCompact` | 未コミット変更と `.compaction-notes.md` を圧縮保護指示として注入 | `CONTEXT_KEEPER_DISABLE_COMPACTION_GUARD=1` |
| `Stop` | Claude が `.claude/session-summary.md` にセッションサマリを生成 | — |
| `SessionStart` | 24h 以内の `.claude/session-summary.md` を次セッションに注入 | `CONTEXT_KEEPER_DISABLE_SESSION_RELAY=1` |

## .compaction-notes.md の書き方

プロジェクトルートに `.compaction-notes.md` を置くと、コンテキスト圧縮時に保護指示として自動で渡されます。

```markdown
# compaction-notes
- 現在 Issue #42 の実装中（auth ミドルウェアのリファクタ）
- `src/middleware/auth.ts` が未完成
- TODO: テストカバレッジを 80% 以上にする
```

## gitignore 推奨設定

個人の作業状態を共有しないため、以下を `.gitignore` に追加することを推奨します:

```
.claude/session-summary.md
.claude/compaction-snapshots/
```

## 各機能の動作条件

- **git/jj 注入**: 変更ファイルがゼロの場合は何も注入しません（トークン節約）
- **圧縮ガード**: 未コミット変更も `.compaction-notes.md` もない場合は何も注入しません
- **セッションリレー**: `.claude/session-summary.md` が存在しない、または 24 時間以上前の場合は注入しません

## 手動でサマリを確認・編集する場合

Stop フックが自動生成したサマリは `.claude/session-summary.md` に保存されます。
内容を確認・修正するには、このファイルを直接編集してください。次の SessionStart 時に内容が読み込まれます。
