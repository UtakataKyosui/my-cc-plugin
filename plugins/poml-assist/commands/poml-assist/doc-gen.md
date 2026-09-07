---
description: ドキュメント生成用 POML テンプレートを使って対象から Markdown ドキュメントを生成する
argument-hint: "<対象ファイルパスまたは説明>"
allowed-tools: Read, Write, Bash, AskUserQuestion
---

# poml-assist: doc-gen

`templates/doc-gen.poml` テンプレートを使ってコード・設計書・要件定義から Markdown ドキュメントを生成します。

## フェーズ 0: 引数確認

`$ARGUMENTS` を確認する:
- **引数あり**: ドキュメント生成対象として使用
- **引数なし**: エラーメッセージを表示して終了

  ```
  使い方: /poml-assist:doc-gen <対象ファイルパスまたは説明>
  例: /poml-assist:doc-gen src/api/users.ts
  ```

## フェーズ 1: 追加情報の確認

`AskUserQuestion` を使って以下を確認する:

- **question**: 「生成するドキュメントの種別を選んでください」
  - options: 「API リファレンス」「チュートリアル/ハンズオン」「設計書/アーキテクチャ」「README」
- **question**: 「読み手（対象読者）を教えてください」
  - options: 「エンジニア（実装者）」「エンジニア（利用者）」「非エンジニア（ビジネス担当）」「その他」

## フェーズ 2: テンプレートのレンダリング

`@skills/poml-guide/poml-template-runner.md` の手順に従い、`templates/doc-gen.poml` を以下の変数でレンダリングする:

- `target`: `$ARGUMENTS`
- `doc_type`: フェーズ 1 で選択したドキュメント種別
- `audience`: フェーズ 1 で選択した読み手

`poml` CLI の有無による分岐とフォールバックは共通ランナー側で扱う。

## フェーズ 3: ドキュメント生成

レンダリングされたプロンプトを元に対象を Read してドキュメントを生成する。

生成後に `AskUserQuestion` で出力先を確認する:

- **question**: 「生成したドキュメントをファイルに保存しますか？」
  - options: 「はい（ファイルパスを指定する）」「いいえ（画面に表示するだけ）」

保存する場合はファイルパスを確認して Write で書き出す。
