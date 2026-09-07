---
description: コード実装・リファクタ用 POML テンプレートを使って実装指示を構造化する
argument-hint: "<要件の説明>"
allowed-tools: Read, Write, Bash
---

# poml-assist: implement

`templates/implement.poml` テンプレートを使ってコード実装・リファクタ指示を構造化します。

## フェーズ 0: 引数確認

`$ARGUMENTS` を確認する:
- **引数あり**: 要件の説明として使用
- **引数なし**: エラーメッセージを表示して終了

  ```
  使い方: /poml-assist:implement <要件の説明>
  例: /poml-assist:implement "ユーザー一覧取得 API を追加する"
  ```

## フェーズ 1: テンプレートのレンダリング

`@skills/poml-guide/poml-template-runner.md` の手順に従い、`templates/implement.poml` を以下の変数でレンダリングする:

- `requirement`: `$ARGUMENTS`
- `target`: 対象ファイル/ディレクトリ（指定がなければ「対象ファイルを指定してください」を入れて後続フェーズで確認）
- `constraints`: 既存のコーディング規約（指定がなければ「コーディング規約があれば記述してください」を入れる）

`poml` CLI の有無による分岐とフォールバックは共通ランナー側で扱う。

## フェーズ 2: 実装実行

レンダリングされたプロンプトを元に実装を行う。

- 対象ファイルが指定されていない場合は、要件から推定して確認する
- 実装後は unified diff 形式で変更内容を表示する
- テストが必要な場合は追加テストケースも提示する
