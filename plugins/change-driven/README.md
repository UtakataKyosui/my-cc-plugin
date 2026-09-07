# change-driven プラグイン

jj の **change-driven ワークフロー**（1 Change = 1 責任範囲）を支えるエージェントを、任意のリポジトリで
使えるよう Claude Code プラグインとして配布する。`jj-exec-aliases` マーケットプレイスのプラグイン。

## 同梱エージェント

| エージェント | 役割 |
|---|---|
| `change-planner` | Issue/仕様書を原子的な jj Change に分解し、**スコープマニフェスト** を生成する（writer） |
| `conventional-commit-writer` | 現在の jj Change から Conventional Commits + Issue 番号付きメッセージを起案する |

## 同梱 hook（jj 安全網）

`hooks/` に jj 安全網の hook 群を同梱し、`hooks/hooks.json` で登録する。

| hook | イベント | 役割 |
|---|---|---|
| `jj-block-direct.sh` | PreToolUse (Bash) | `jj new` / `jj git push` の直接実行を **ブロック**し `jj safe-new` / `jj safe-push` へ誘導（exit 2）。`jj safe-*` と `command jj …` は通過。`jq` 不在は **fail-open**（exit 0） |
| `jj-task-start.sh` | PostToolUse (TaskUpdate) | タスクが `in_progress` になったら `jj safe-new -m "<title>"` で次の Change を起動（**ベストエフォート**・常に exit 0） |
| `jj-error-advisor.sh` | PostToolUseFailure (Bash) | `jj` コマンド失敗時にサブコマンド別の復旧ヒントを表示（常に exit 0） |
| `jj-workspace-detect.sh` | CwdChanged | ディレクトリ移動時に jj リポを検出し現在の change / bookmark を表示（常に exit 0） |

ブロック以外の 3 つは **絶対にブロックしない**（助言・補助のみ）。`jj-block-direct` だけが
`exit 2` で実行を止める。`jj-task-start` は load-bearing ではない補助で、安全網の強制は
`jj-block-direct`（と任意のシェルラッパー）が担う。`CwdChanged` は harness 依存
（`claude plugin validate` は通過する）。

> **前提（重要）**: これら hook の誘導先である `jj safe-new` / `jj safe-push` は、本プラグインには
> **含まれない**。`jj-exec-aliases` リポジトリの `just sync` で別途インストールするエイリアスである。
> プラグインだけを入れて `just sync` を実行していない場合、`jj new` はブロックされるのに誘導先の
> エイリアスが存在しない、という状態になる。**完結した安全網にするには両方を入れること**
> （`just sync` でエイリアス＋本プラグインで block hook）。リポジトリ側 README の
> 「`jj` 安全網のセットアップ」を参照。

## インストール

```text
# マーケットプレイスを追加（GitHub から）/ プラグインをインストール（Claude Code TUI コマンド。シェルではない）
/plugin marketplace add UtakataKyosui/jj-exec-aliases
/plugin install change-driven@jj-exec-aliases
```

インストール後、エージェントは `/agents` に `change-driven:change-planner` /
`change-driven:conventional-commit-writer` として現れ、Claude が文脈に応じて自動起動する。

## スコープマニフェストの場所（reader との整合）

`change-planner` が生成するスコープマニフェストは、`jj-exec-aliases` の `safe-new` エイリアス（reader）が
読むのと **同じパス** に書かれる。両者が食い違わないよう、writer は同梱の共有リゾルバ
`scripts/scope-manifest-path.sh` を `$CLAUDE_PLUGIN_ROOT` 経由で呼び出す。

- 既定: `${XDG_STATE_HOME:-$HOME/.local/state}/jj-safe-new/<repo-id>.json`（リポジトリ外。誤コミット防止）
- override: `JJ_SCOPE_FILE` を設定するとそのパスが優先される

> マニフェストを生成するだけでスコープチェックが効くわけではない。**reader 側**（`jj safe-new` エイリアス）は
> このプラグインには含まれない。スコープチェックまで効かせるには `jj-exec-aliases` リポジトリの
> `just sync` で `safe-new` エイリアスを別途インストールする。仕様は同梱の
> [`docs/scope-manifest.md`](./docs/scope-manifest.md) を参照。

## 同梱物

```
plugins/change-driven/
├── .claude-plugin/plugin.json          # プラグインマニフェスト
├── agents/
│   ├── change-planner.md               # writer エージェント
│   └── conventional-commit-writer.md   # commit メッセージ起案エージェント
├── hooks/
│   ├── hooks.json                      # 4 hook の登録（自動検出される既定パス）
│   └── scripts/
│       ├── jj-block-direct.sh          # PreToolUse: jj new / jj git push の直接実行ブロック
│       ├── jj-task-start.sh            # PostToolUse(TaskUpdate): in_progress で safe-new 起動
│       ├── jj-error-advisor.sh         # PostToolUseFailure: jj 失敗時の復旧ヒント
│       └── jj-workspace-detect.sh      # CwdChanged: jj リポ検出
├── scripts/scope-manifest-path.sh      # パス解決の共有リゾルバ（$CLAUDE_PLUGIN_ROOT 経由）
└── docs/scope-manifest.md              # スコープマニフェスト仕様
```

`agents/` `scripts/` `docs/` の各ファイルは repo ルートの正本（`.claude/agents/`・`scripts/`・`docs/`）の
ミラー。`just plugin-sync` で再生成し、`just plugin-check`（CI でも実行）で乖離を検知する。**この配下を
直接編集せず、正本を編集して `just plugin-sync` を実行すること。**

`hooks/` と `.claude-plugin/plugin.json` は **プラグイン固有**（ミラー対象外。repo ルートに正本を持たない）。
hook の挙動は `just hooks-check`（CI でも実行）でスモークテストする。`hooks/hooks.json` は
Claude Code が自動検出する既定パスのため、`plugin.json` に `hooks` フィールドは置かない（重複登録になる）。
