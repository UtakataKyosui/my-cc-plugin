# スコープマニフェスト

## 概要

スコープマニフェストは各 Change の **責任範囲** を宣言する JSON ファイル。
`jj safe-new` がこれを読み込み、スコープ外のファイルが変更されていないかチェックする。
`change-planner` エージェントが生成する（writer）。

> このリポジトリの safe-new はマニフェストを **リポジトリ外** に置く（誤コミット防止）。旧
> issue-driven-flow プラグインの `.claude/jj-scope.json`（repo 内）から移行したもの。

## 置き場所

writer（`change-planner`）と reader（`jj safe-new`）は **同じ解決規則** で 1 つのパスを指す。
共有リゾルバ `scripts/scope-manifest-path.sh` がそのパスを出力する:

1. `JJ_SCOPE_FILE` が設定されていればそのパス（override）。
2. 未設定なら repo 単位のファイルを XDG state ディレクトリ配下に置く（repo 外）:

   ```
   ${XDG_STATE_HOME:-$HOME/.local/state}/jj-safe-new/<repo-id>.json
   ```

   `<repo-id>` は workspace root の絶対パスから導出（`<basename>-<hash[:16]>`）。
   `<hash>` は `shasum`／`sha1sum` があれば SHA-1、いずれも無い環境では `cksum`
   にフォールバックする（`scripts/scope-manifest-path.sh` と `aliases/safe-new/run.sh` で同一）。

## ファイル形式

```json
{
  "<Change1 の description>": ["<許可ファイル1>", "<許可ファイル2>"],
  "<Change2 の description>": ["<許可ファイル3>"]
}
```

- **キー**: `jj describe -m "..."` に渡した description の **第1行**（`description.first_line()`）と完全一致させる。reader は第1行をキーに引くため、複数行 description では2行目以降は照合に使われない
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
2. マニフェストでその description をキーに許可ファイル一覧を取得
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
3. マニフェストにそのファイルを追加する（責任範囲に含める場合）

## マニフェストが存在しない場合

manifest 不在時の挙動は使用している safe-new alias の版に従う（詳細は
`aliases/safe-new/README.md`）。スコープを既定で必須とする版では manifest 不在をブロックし
`JJ_SCOPE_OPTIONAL=1` でスキップできる。スコープを任意とする版では manifest 不在時はチェックを
スキップし、品質ゲートのみ実行する。いずれの版でも、スコープを効かせるには先にマニフェストを
作成してから `jj safe-new` を実行する。

## コミットしないこと

マニフェストは **リポジトリ外**（XDG state ディレクトリ配下）に置かれるため、リポジトリには
コミットされない。これは「Issue 単位の一時的な計画状態をワーキングコピーに残して誤コミットする」
リスクを避けるための設計（jj-exec-aliases Issue #5/#8）。設計意図を残したい場合は PR 説明や
Issue にスコープ分解を記述する。
