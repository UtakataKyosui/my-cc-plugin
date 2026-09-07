---
description: poml-reviewer エージェントを呼び出してファイルをレビューする（.poml なら構造レビュー、それ以外ならコードレビュー）
argument-hint: "<ファイルパス>"
allowed-tools: Read, Task
---

# poml-assist: review

`poml-reviewer` エージェントを呼び出してファイルをレビューします。

- 対象が `.poml` ファイルなら **POML 構造レビュー**（タグ構造・三点セット・`<example>` 数など）
- それ以外のソースコードなら **コードレビュー**（`templates/review.poml` 指示に従って ERROR/WARNING/INFO の 3 段階）

## フェーズ 0: 引数確認

`$ARGUMENTS` を確認する:
- **引数あり**: レビュー対象ファイルパスとして使用
- **引数なし**: エラーメッセージを表示して終了

  ```
  使い方: /poml-assist:review <ファイルパス>
  例:
    /poml-assist:review src/api/users.ts        # コードレビュー
    /poml-assist:review prompts/summarize.poml  # POML 構造レビュー
  ```

## フェーズ 1: ファイル存在確認

対象ファイルが存在するか確認する。存在しない場合はエラーを表示して終了する。

## フェーズ 2: poml-reviewer エージェントの呼び出し

`Task` ツールで `poml-reviewer` エージェントを起動する:

```
Task(
  subagent_type="poml-reviewer",
  description="ファイルレビュー",
  prompt="次のファイルをレビューしてください: $ARGUMENTS"
)
```

エージェントが拡張子に応じてレビューモードを判別し、結果を返す。

## フェーズ 3: 結果の提示

エージェントの返り値をそのままユーザーに提示する。コマンドは結果に追加の解釈・要約を加えない。
