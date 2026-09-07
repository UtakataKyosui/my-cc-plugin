# POML インライン記法スタイルガイド

Claude Code のプロンプト本文に POML タグを直接書く「インライン運用」のルールを定義する。

## タグ化する/しない判断基準

### タグ化する（POML を使う）条件

| 条件 | 理由 |
|---|---|
| 指示が 5 行を超える | 長文は構造化すると Claude が解釈しやすい |
| good/bad の比較例を含む | `<example type="positive/negative">` で意図が明確になる |
| 複数の条件・ステップが絡む | `<task>` 内で条件や手順を構造化して優先度を明示 |
| 出力フォーマットを厳密に制御したい | `<output-format>` で形式を固定 |
| 複数プロンプトで同じ構造を再利用する | `<let>` で変数化して `.poml` ファイル化 |

### タグ化しない（プレーンテキストで書く）条件

| 条件 | 例 |
|---|---|
| 3 行以内の単純指示 | 「このコードのバグを直して」 |
| 一回限りの質問 | 「この変数名の意図を教えて」 |
| 構造が不要な短いフォローアップ | 「もっと簡潔に書いて」 |

## 最小三点セット

`<role>` + `<task>` + `<output-format>` の三点セットを最小構成とする。

```xml
<poml>
  <role>あなたはシニアエンジニアです。</role>
  <task>以下のコードをレビューしてください。</task>
  <output-format>ERROR / WARNING / INFO の 3 段階で出力してください。</output-format>
</poml>
```

**three-point rule**: この 3 タグが揃っていれば、Claude の回答品質のブレを最小化できる。

## `<example>` の使い方

- `<example>` は **good/bad 各 1 個まで** に制限する（多すぎるとコンテキストを圧迫する）
- `type="positive"` = 期待する出力、`type="negative"` = 避けてほしい出力

```xml
<example type="positive">
  <input>バグを直して</input>
  <output>diff 形式で修正箇所を示し、理由を 1 文で説明する</output>
</example>
<example type="negative">
  <input>バグを直して</input>
  <output>長い解説の後にコード全体を貼り直す（変更点が不明瞭）</output>
</example>
```

## 既存リファレンスとの読み分け

| ドキュメント | 用途 |
|---|---|
| [poml-tags-reference.md](./poml-tags-reference.md) | 全タグの属性仕様を調べる |
| [poml-syntax.md](./poml-syntax.md) | テンプレート変数・条件分岐・ループの書き方 |
| [poml-patterns.md](./poml-patterns.md) | 用途別の設計パターン集 |
| **このファイル** | プロンプト本文にタグを書くか否かの判断基準 |

## インライン記法の例

### タグなし（プレーンテキスト）

```
このファイルのバグを直して
```

### タグあり（5 行超・出力形式あり）

```xml
<poml>
  <role>シニアエンジニアとして振る舞ってください。</role>
  <task>
    以下のファイルに含まれるバグを修正してください。
    セキュリティ脆弱性がある場合は ERROR として分類してください。
    既存のコーディング規約（ESLint 設定準拠）を維持してください。
  </task>
  <output-format>
    unified diff 形式で変更を示し、各修正に理由を 1 文添えてください。
  </output-format>
</poml>
```
