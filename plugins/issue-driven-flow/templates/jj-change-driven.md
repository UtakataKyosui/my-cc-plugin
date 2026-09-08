## 実装の進め方

Issueや仕様書を実装する場合、以下の手順で進めること。

### 計画フェーズ（実装前に必ず行う）

1. EnterPlanMode で Issue を読み、実装を原子的な `Change` に分解する（1 Change = 1つの変更責任）
2. ExitPlanMode で計画をユーザーに提示し、承認を得る
3. 承認後、各 Change を TaskCreate でタスクとして登録する
4. `.claude/jj-scope.json` を作成し、タスク名をキーに変更してよいファイル一覧を記録する

### 実行フェーズ

1. TaskUpdate でタスクを `in_progress` にする（PostToolUse Hook が `jj safe-new -m "<タスク名>"` を自動実行する）
2. 実装する（`.claude/jj-scope.json` に記載されたファイルのみ変更する）
3. 次のタスクを `in_progress` にする → 繰り返す

または手動で:

1. Change の開始時に責任範囲を宣言する: `jj describe -m "<タスク名>"`
2. 実装する
3. 次の Change へ移る: `jj safe-new -m "<次のタスク名>"`
   （スコープチェック → 品質チェックが自動実行される。失敗時は修正して再実行）

### Push

- すべての実装が終わったら `jj safe-push` でプッシュする
- jj-exec-aliases 導入時は `jj new` / `jj git push` の代わりに `jj safe-new` / `jj safe-push` alias を使う（シェルラッパー導入時は透過リダイレクトされる）。未導入時は通常の `jj new` / `jj git push` を使う
