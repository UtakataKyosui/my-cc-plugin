# poml-assist

Microsoft POML（Prompt Orchestration Markup Language）を活用したプロンプト設計支援プラグイン。

対話フローによる POML プロンプトの生成、構文リファレンスへのアクセス、ファイル保存時の自動バリデーション・レンダリングプレビューを提供する。

## 機能

| 機能 | 説明 |
|---|---|
| **対話フロー** | `/poml-assist:create-poml` コマンドで段階的な質問に答えながら POML を生成 |
| **実装テンプレート** | `/poml-assist:implement` でコード実装・リファクタ指示を diff 形式で構造化 |
| **レビューテンプレート** | `/poml-assist:review <ファイル>` で `poml-reviewer` エージェントが対応モードを判別（`.poml` なら構造レビュー、それ以外ならコードレビュー） |
| **ドキュメント生成** | `/poml-assist:doc-gen` でコード・設計書から Markdown ドキュメントを生成 |
| **構文リファレンス** | `.poml` ファイル編集時や POML 関連の質問時に自動でスキルが起動 |
| **インライン記法ガイド** | `poml-inline-style.md` でプロンプト本文への直書き運用ルールを提供 |
| **自動バリデーション** | `.poml` ファイル保存時に `poml check` を自動実行 |
| **レンダリングプレビュー** | `.poml` ファイル保存時に `poml render` でプレーンテキストプレビューを表示 |
| **POML / コードレビュー** | `poml-reviewer` エージェントが拡張子で判別し、`.poml` は構造レビュー・それ以外はコードレビューを 3 段階でレポート |

## インストール要件

バリデーション・レンダリングフックには `poml` CLI が必要:

```bash
pip install poml
```

## 使い方

### コマンド: POML の対話的作成

```
/poml-assist:create-poml
```

または出力ファイルパスを指定:

```
/poml-assist:create-poml prompts/summarize.poml
```

6 フェーズの対話フローで POML プロンプトを作成する:
1. 用途・ペルソナ・入力データの確認
2. 出力形式・Few-shot サンプルの確認
3. テンプレート変数の確認（オプション）
4. POML 生成とプレビュー
5. ファイル保存
6. レビュー案内

### コマンド: 用途別テンプレートで素早く構造化

#### コード実装・リファクタ

```
/poml-assist:implement <要件の説明>
```

例: `/poml-assist:implement "ユーザー一覧取得 API を追加する"`

`templates/implement.poml` を使い、差分形式で実装指示を構造化する。`<role>` 実装担当 + `<task>` + `<hint>` 規約 + `<example>` good/bad + `<output-format>` diff 形式。

#### コード / POML レビュー

```
/poml-assist:review <ファイルパス>
```

例:
- `/poml-assist:review src/api/users.ts` → コードレビュー（`templates/review.poml` 適用、ERROR/WARNING/INFO の 3 段階）
- `/poml-assist:review prompts/summarize.poml` → POML 構造レビュー（タグ構造・三点セット・`<example>` 数チェック）

コマンドは `poml-reviewer` エージェントを呼び出す薄ラッパーで、エージェント側が拡張子に応じてモードを切り替える。

#### ドキュメント生成

```
/poml-assist:doc-gen <対象ファイルパスまたは説明>
```

例: `/poml-assist:doc-gen src/api/users.ts`

`templates/doc-gen.poml` を使い、API リファレンス・チュートリアル・設計書・README などを Markdown 章立てで生成する。`<stylesheet>` でトーン・言語・フォーマットを制御。

### スキル: POML 構文リファレンス

以下のいずれかで自動起動:
- `.poml` ファイルを開いている状態での質問
- 「POML とは」「POML の書き方」「role タグ」などの質問

提供するリファレンス:
- `poml-syntax.md` - ファイル構造・テンプレート変数・条件分岐・ループ
- `poml-tags-reference.md` - 全タグの属性仕様と使用例
- `poml-patterns.md` - 用途別設計パターン集（7 パターン）
- `poml-stylesheet.md` - `<stylesheet>` によるフォーマット制御
- `poml-inline-style.md` - プロンプト本文へのインライン記法運用ガイド

### エージェント: POML 自動生成

`poml-architect` エージェントが `/poml-assist:create-poml` コマンドから呼び出され、要件を分析して最適な POML 構造を設計・生成する。

### エージェント: POML / コードレビュー

```
POMLファイルをレビューして
src/api/users.ts をレビューして
```

`poml-reviewer` エージェントは入力ファイルの拡張子で動作モードを切り替える:

- `.poml` → POML 構造レビュー（三点セット・`<example>` 数・タグネスト等を 3 段階でチェック）
- それ以外 → `templates/review.poml` を適用してソースコードを ERROR/WARNING/INFO で指摘

`/poml-assist:review` コマンドはこのエージェントを呼び出す薄いラッパーとして機能する。

### フック: 自動バリデーション・プレビュー

`.poml` ファイルを保存（Write/Edit）すると自動実行:
1. `validate-poml.py` - `poml check` によるバリデーション
2. `render-poml.py` - `poml render` によるプレーンテキストプレビュー（先頭 300 文字）

フックは advisory のみ（常に exit 0）でブロックしない。

## POML とは

Microsoft が開発した XML 形式のマークアップ言語。AI Agent への構造化した指示記述に使用する。

```xml
<poml>
  <role>あなたは優秀な編集者です。</role>
  <task>以下のテキストを200文字以内で要約してください。</task>
  <output-format>要約文のみを出力。</output-format>
</poml>
```

詳細: https://github.com/microsoft/poml

## ディレクトリ構成

```
plugins/poml-assist/
├── .claude-plugin/plugin.json    # プラグイン設定
├── skills/poml-guide/            # POML 構文リファレンス
│   ├── SKILL.md                  # スキル設定・クイックリファレンス
│   ├── poml-syntax.md            # 構文詳細
│   ├── poml-tags-reference.md    # タグリファレンス
│   ├── poml-patterns.md          # 設計パターン集
│   ├── poml-stylesheet.md        # stylesheet ガイド
│   ├── poml-inline-style.md      # インライン記法スタイルガイド
│   └── poml-template-runner.md   # テンプレートレンダリング共通手順
├── templates/
│   ├── implement.poml             # コード実装・リファクタ用テンプレート
│   ├── review.poml                # レビュー・分析用テンプレート
│   └── doc-gen.poml               # ドキュメント生成用テンプレート
├── commands/poml-assist/
│   ├── create-poml.md             # 対話的 POML 生成コマンド
│   ├── implement.md               # 実装テンプレート呼び出しコマンド
│   ├── review.md                  # レビューテンプレート呼び出しコマンド
│   └── doc-gen.md                 # ドキュメント生成テンプレート呼び出しコマンド
├── agents/
│   ├── poml-architect.md         # POML 生成エージェント
│   └── poml-reviewer.md          # POML レビューエージェント
├── hooks/
│   ├── hooks.json                # フック設定
│   └── scripts/
│       ├── validate-poml.py      # バリデーションスクリプト
│       └── render-poml.py        # レンダリングプレビュースクリプト
└── README.md
```
