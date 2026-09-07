# POML テンプレートランナー（共通手順）

`templates/*.poml` を Claude のプロンプトに注入するための共通手順。`/poml-assist:implement` `/poml-assist:doc-gen` などのコマンドから参照される。

## 適用条件

以下のいずれかに該当するコマンドの「テンプレートをレンダリングしてプロンプトを構築する」フェーズで本手順を再利用する:

- 引数（`$ARGUMENTS` など）を受け取って、`templates/<name>.poml` の `{{var}}` を置換した結果を Claude のプロンプトとして使いたい
- `poml` CLI が利用可能なら使い、未インストールでも動作させたい

## 手順

### Step 1: `poml` CLI の有無を確認

```bash
which poml 2>/dev/null || echo "not_found"
```

### Step 2-A: `poml` CLI が利用可能な場合

`poml render` で変数置換 + バリデーションを実行する:

```bash
poml render ${CLAUDE_PLUGIN_ROOT}/templates/<name>.poml \
  --var "key1=value1" \
  --var "key2=value2"
```

レンダリング結果（プレーンテキスト）を Claude が後続のプロンプトとして解釈する。

### Step 2-B: `poml` CLI が利用不可の場合

1. `Read` ツールで `${CLAUDE_PLUGIN_ROOT}/templates/<name>.poml` を読み込む
2. テンプレート内の `{{key1}}` `{{key2}}` などを引数の値で文字列置換する
3. `<example>` `<role>` `<task>` などの XML 構造はそのまま残す（Claude は POML タグを理解できる）
4. 置換結果をプロンプトとして使う

### Step 3: 検証（任意・推奨）

レンダリング後の出力に未置換の `{{}}` が残っていないかチェックする。残っている場合は変数指定漏れなのでユーザーに追加情報を求める。

## エラーハンドリング

| 状況 | 対応 |
|---|---|
| テンプレートファイルが存在しない | エラーメッセージで終了。プラグインの再インストールを案内 |
| `poml render` がエラー終了 | フォールバックで Step 2-B（手動置換）に切り替える |
| 必須変数が未指定 | 該当変数を `AskUserQuestion` でユーザーに確認 |

## 呼び出し側コマンドへの推奨記述

各コマンド `.md` の Phase 2 を以下のように簡素化できる:

```markdown
## フェーズ 2: テンプレートのレンダリング

`@skills/poml-guide/poml-template-runner.md` の手順に従い、
`templates/<name>.poml` を以下の変数でレンダリングする:

- `<var1>`: <値の説明>
- `<var2>`: <値の説明>
```

これにより各コマンドのボイラープレート（`which poml` 分岐・フォールバック手順）が一箇所に集約される。
