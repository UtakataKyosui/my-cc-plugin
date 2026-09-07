---
name: obsidian-semantic-search
description: >
  Obsidian Vault をローカル埋め込みモデルで意味検索（セマンティック検索）し、
  関連ノートをファイルパス付きで特定する。「意味で検索して」「似た内容のノートある？」
  「曖昧だけど関連知識を探して」「キーワードが思い出せないけど前に書いた」といった、
  全文一致では拾えない検索に使用する。キーワード完全一致でよい場合は obsidian-recall を使う。
---

# obsidian-semantic-search

ユーザーの意図を凝縮したクエリで Vault を意味検索し、上位ノートを読み込んで作業に活かす。
検索は LLM ではなく独立した Python エンジン（`bin/oss`）が行う。Claude は CLI を呼んで
JSON を受け取り、関連ファイルを Read するだけ。

## 前提

このプラグインの `bin/oss` を使う。`${CLAUDE_PLUGIN_ROOT}/bin/oss` で解決できる。
未セットアップなら初回のみ `bash "${CLAUDE_PLUGIN_ROOT}/setup.sh"` が必要。

## 手順

1. **状態を確認する**（モデルを読み込まないので高速）

   ```bash
   "${CLAUDE_PLUGIN_ROOT}/bin/oss" status --json
   ```

   - `missing_index: true` → 初回セットアップを実行する:

     ```bash
     bash "${CLAUDE_PLUGIN_ROOT}/setup.sh"
     "${CLAUDE_PLUGIN_ROOT}/bin/oss" index --full
     ```

   - `stale > 0` → 必要に応じて増分更新する（`bin/oss index`）。

2. **意味検索する**

   ```bash
   "${CLAUDE_PLUGIN_ROOT}/bin/oss" query "<ユーザーの意図を凝縮したクエリ>" --json --top-k 5
   ```

   クエリはユーザーの言葉そのままではなく、検索意図を表す自然文に凝縮する
   （例: 「前にフックが settings に未接続だった話」→「Claude Code フック settings 未接続 問題」）。

3. **結果の JSON をパースし、関連ノートを読み込む**

   - 各 result は `{path, score, heading, line_start, snippet}`。
   - `path` を **Read ツールでそのまま開く**（`line_start` 周辺を優先。パスにスペースや日本語が
     含まれても加工しない）。
   - `score` が低い（目安 < 0.3）結果は提示にとどめ、Read しない。

4. **読み込んだ内容を踏まえて回答・作業する**

## 使い分け

- 概念的・曖昧・言い換えを含む検索 → このスキル（意味検索）。
- キーワードが明確で完全一致でよい → `obsidian-recall`（Obsidian CLI の全文検索）。

## 出力例

```json
{"query":"Claude Code フック settings 未接続","model":"intfloat/multilingual-e5-small",
 "results":[{"path":"knowledge/claude-code/運用ギャップ分析-2026-04.md","score":0.82,
   "heading":"既存のギャップ分析との関係","line_start":17,"snippet":"…"}]}
```
