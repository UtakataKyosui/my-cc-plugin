# スコープマニフェスト (.claude/jj-scope.json)

## 概要

`.claude/jj-scope.json` は各 Change の **責任範囲** を宣言するファイル。
`jj safe-new` がこのファイルを読み込み、スコープ外のファイルが変更されていないかチェックする。

## ファイル形式

```json
{
  "<Change の description>": ["<許可ファイル1>", "<許可ファイル2>"],
  "<Change の description>": ["<許可ファイル3>"]
}
```

- **キー**: `jj describe -m "..."` に渡した description と完全一致させる
- **値**: その Change で変更を許可するファイルのパス一覧（リポジトリルートからの相対パス）

## 実例

```json
{
  "feat: User modelとDBスキーマを追加": [
    "src/models/user.ts",
    "prisma/schema.prisma"
  ],
  "feat: 認証APIエンドポイントを追加": [
    "src/api/auth.ts"
  ],
  "feat: セッションミドルウェアを追加": [
    "src/middleware/session.ts"
  ],
  "test: Integration testを追加": [
    "tests/auth.test.ts"
  ]
}
```

## Claude による生成

計画フェーズでユーザーが承認した後、Claude が自動生成する。
`change-planner` エージェントを使うと Issue から自動で生成できる。

## スコープチェックの動き

`jj safe-new` 実行時:

1. `jj log -r @ --no-graph -T 'description.first_line()'` で現在の description の第1行を取得
2. `jj-scope.json` でその description をキーに許可ファイル一覧を取得
3. `jj diff --name-only` で実際に変更されたファイルを取得
4. スコープ外ファイルがあれば error メッセージを出して exit 1

## スコープ違反の対処

```
✗ スコープ外のファイルが変更されています:
  - src/api/other.ts
このChangeの責任範囲を確認し、別のChangeに切り出してください。
```

対処方法:
1. `jj diff src/api/other.ts` でどんな変更か確認
2. `jj split` で変更を別 Change に切り出す
3. `jj-scope.json` にそのファイルを追加する（責任範囲に含める場合）

## マニフェストが存在しない場合

`.claude/jj-scope.json` が存在しない場合はスコープチェックをスキップして
`jj fix` のみ実行する。スコープ管理が不要なプロジェクトでも `jj safe-new` は使える。

## ファイルのコミット

`.claude/jj-scope.json` はリポジトリにコミットすることを推奨する。
これにより Change の設計意図がコミット履歴と共に残る。
