# スコープマニフェスト

スコープマニフェストの唯一の writer は `change-driven:change-planner` です。
`issue-driven-flow` はこの定義を複製しません。`change-driven` プラグインをインストールし、
エージェントの指示に従ってマニフェストを生成してください。

マニフェストはリポジトリ外の per-repo パスに保存され、`jj safe-new` が同じパスを読み取ります。
固定の `.claude/jj-scope.json` は使用しません。
