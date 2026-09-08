---
name: conventional-commits
description: >
  Conventional Commits 規約と Issue 番号付与ルールのリファレンス。
  このプラグインで強制するコミットメッセージ形式の完全ガイド。
  コミットメッセージを書くとき、Lefthook エラーが出たとき、type/scope を迷ったときに参照する。
---

# Conventional Commits ガイド（issue-driven-flow 版）

## フォーマット

```
<type>(<scope>): <subject> (#NNN)

<body（任意）>

<footer（任意）>
```

### 必須要素

| 要素 | 形式 | 例 |
|---|---|---|
| type | 下表参照 | `feat` |
| scope | 変更領域（任意だが推奨） | `auth` |
| subject | 50 字以内、命令形、末尾ピリオドなし | `ログイン機能を追加する` |
| (#NNN) | Issue 番号必須（Lefthook が強制） | `(#123)` |

### type 一覧

| type | 使う場面 | semver への影響 |
|---|---|---|
| `feat` | 新機能追加 | MINOR |
| `fix` | バグ修正 | PATCH |
| `docs` | ドキュメントのみ | なし |
| `style` | フォーマット・空白（機能変更なし） | なし |
| `refactor` | リファクタリング（feat でも fix でもない） | なし |
| `perf` | パフォーマンス改善 | PATCH |
| `test` | テストの追加・修正 | なし |
| `build` | ビルドシステム・依存関係 | なし |
| `ci` | CI 設定ファイル | なし |
| `chore` | その他（src/test 以外）の変更 | なし |
| `revert` | 以前のコミットを revert | PATCH |

### scope の決め方

共有スコープマニフェストの現 Change キーが scope の基準：

```json
{
  "feat: 認証モジュールを追加する": ["src/auth/", "tests/auth.test.ts"]
}
```

→ scope は `auth`

ファイルが複数ディレクトリにまたがる場合は最も重要なドメインを選ぶ。

## 例

```
feat(auth): JWT ログイン機能を実装する (#42)
fix(api): null ポインタ参照を修正する (#67)
docs(readme): セットアップ手順を更新する (#80)
refactor(db): クエリビルダーを共通化する (#91)
test(auth): ログアウトフローの Integration テストを追加する (#42)
```

## BREAKING CHANGE

```
feat(api)!: v2 API エンドポイントに移行する (#100)

BREAKING CHANGE: /v1/users は廃止されました。/v2/users を使用してください。
```

`!` サフィックスまたは `BREAKING CHANGE:` フッターで MAJOR バンプを示す。

## Lefthook による二段強制

### Stage 1: prepare-commit-msg
ブランチ名（`feat/123-auth`）から Issue 番号を自動検出し、メッセージ末尾に `(#123)` を補完する。

### Stage 2: commit-msg
正規表現でメッセージ形式を検証する:
```
^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?: .+ \(#\d+\)$
```

### スキップが必要な場合
```bash
# 初期コミット・リポジトリ移行など、Issue 番号が存在しない場合のみ
SKIP=commit-msg lefthook run commit-msg
```

## `conventional-commit-writer` エージェントとの連携

`/issue-driven-flow:commit-change` コマンドを使うと、`conventional-commit-writer` エージェントが：

1. `jj diff` を分析してコミット内容を理解
2. ブランチ名から Issue 番号を抽出
3. 共有スコープマニフェストで scope を特定
4. `gh issue view` で Issue の文脈を取得
5. 上記規約に従ったメッセージを起案

人間は確認・微調整するだけで済む。
