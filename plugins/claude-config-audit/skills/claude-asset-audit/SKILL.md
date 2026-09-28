---
name: claude-asset-audit
description: 設置済みの Skills / Rules / SubAgents / Hooks / Commands / OutputStyles を Anthropic の Opus 5・Sonnet 5 プロンプト指針に照らして棚卸しする。フロントマターの黙って壊れる書き方、過剰検証を招く指示、レビューの recall を落とす重要度フィルタ、引き継いだままの effort を機械的に洗い出し、判断が要る観点はチェックリストで詰める。「Skill や Rules を見直したい」「Opus 5 / Sonnet 5 向けに設定を点検して」と言われたときに使う。
---

# claude-asset-audit

`~/.claude` に置いた資産を、Anthropic 公式のモデル別プロンプト指針に照らして棚卸しする。

- Opus 5: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5
- Sonnet 5: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-sonnet-5

検査は2層に分かれる。機械で判定できるものはスクリプトが出し、設計意図の判断が要るものは
`references/checklist.md` を読んで人とモデルが詰める。この分離を崩さない。
機械層に判断を持ち込むと誤検知が増え、レポート全体が読まれなくなる。

## 手順

1. 機械層を実行する。

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/skills/claude-asset-audit/audit.sh
   ```

   手動実行時、`${CLAUDE_PLUGIN_ROOT}` の実パスは
   `~/.claude/plugins/cache/<marketplace>/claude-config-audit/<version>` 配下になる
   （`~/.claude/plugins/installed_plugins.json` の `installPath` で確認できる）。

2. 出力の ERROR を先に片付ける。ERROR は「黙って壊れている」ものだけを入れてある。
3. WARN と INFO を1件ずつ見る。INFO は「意図的ならそのままでよい」もので、
   消すべきものではなく判断を求めるものである。
4. `references/checklist.md` を読み、機械層で拾えない観点を順に見る。
   該当なしの項目も「該当なし」と書き残す。飛ばしたのか見たのかが後から分かるようにする。
5. 変更する資産を決め、1資産1変更で直す。まとめて直すと、どの変更がどの指針に対応したか
   追えなくなる。

## 機械層が見るもの

| 検査 | 重大度 | 何を見るか |
|---|---|---|
| `frontmatter-key` | ERROR | SubAgent の `disallowed-tools`。未知キーとして無視される。正しくは `disallowedTools` |
| `skills-preload` | ERROR | `skills:` があるのに `tools:` に `Skill` が無い / 参照先の Skill が存在しない / 参照先が `disable-model-invocation: true` |
| `skill-name` | ERROR | `name:` の欠落、ディレクトリ名との不一致 |
| `skill-description` | ERROR/WARN | `description:` の欠落、1024 文字超過、起動判断ができない短さ |
| `model-unset` | WARN | SubAgent の `model:` 未指定。セッションのモデルを継承する |
| `self-recheck` | WARN | モデル自身への再確認指示。Opus 5 は指示なしで自己修正する |
| `final-verification-step` | WARN | 独立した検証ステップの指示。Opus 5 では過剰検証になる |
| `severity-filter` | WARN | レビュー段階の重要度フィルタ。literal に守られて recall が落ちる |
| `delegation-cap` | WARN | サブエージェント委譲の上限に触れた資産があるか |
| `subagent-verification` | INFO | サブエージェントに検証を担わせる設計。意図の確認を促す |
| `effort-sweep` | INFO | `agents/*.md` と `agent-routing` のロール定義にある effort の一覧 |
| `disable-model-invocation` | INFO | 安全担保に使っていないか(hook 層でやるべき) |
| `verbosity-control` | INFO/WARN | 応答と成果物の長さを明示している資産があるか |

## ライブラリとして使う

```bash
source ${CLAUDE_PLUGIN_ROOT}/skills/claude-asset-audit/lib/audit.sh
audit_all | audit_report          # Markdown の表にする
audit_skill_frontmatter           # 個別の検査だけ回す
audit_files                       # 走査対象のファイル一覧
```

各検査は `severity<TAB>check<TAB>location<TAB>message` の行を出す。
`audit_report` は標準入力からこの形式を受け取るだけなので、検査を追加しても表側は触らずに済む。

| 環境変数 | 既定 | 効果 |
|---|---|---|
| `AUDIT_ROOT` | `$HOME/.claude` | 走査の起点 |
| `AUDIT_DIRS` | `rules skills agents hooks commands output-styles` | 走査対象のディレクトリ。`*.md` と `*.sh` を走査する |
| `AUDIT_EXCLUDE_RE` | `/skills/claude-asset-audit/` | 走査から外すパスの正規表現 |
| `CLAUDE_ASSET_AUDIT_LIB` | `$AUDIT_ROOT/skills/claude-asset-audit/lib/audit.sh` | `audit.sh` が読むライブラリの位置 |

## 実測で判明した罠

**`plugins/` を走査対象に入れない。** plugin 管理下のファイルはこちらで編集できず、
指摘しても行動に移せない。件数だけが増えてレポートの信号対雑音比が落ちる。
既定の `AUDIT_DIRS` から外してある。

**決定的なツール手順を再確認指示と混同しない。** `self-recheck` と
`final-verification-step` は、行にコマンド名・lint・test・CI・コミットなどが含まれる場合に
その行を捨てる。これが無いと `rules/code-quality.md` の
「linter を実行してからコミットする」や `rules/vcs-jj.md` の
「push 前に `divergent()` を確認する」が全部引っかかる。これらは Opus 5 でも残すべき手順で、
削らせてはいけない。

**「検証用の worktree」は検証指示ではない。** `subagent-verification` は
`検証用` `worktree` `workspace` を含む行を捨てる。この除外が無いと
`rules/parallel-agent-worktree-safety.md` が誤検知になる。日本語の「検証」は
モデルの自己検証と、環境の動作確認の両方を指すため、語だけでは判別できない。

**役割分担の敵対的レビューを禁止事項として扱わない。** Opus 5 の指針が禁じているのは
「自分の作業を自分で検証させる」ことで、一次レビューと反証をロール分けする設計とは別である。
そのため `subagent-verification` は WARN ではなく INFO にしてある。
機械層は衝突しうる箇所を示すだけで、可否は判断しない。

**フロントマターの値はブロックスカラーになりうる。** `description: |` の後に本文が続く形式が
実際に使われている。1行目だけを取ると `|` や空文字が値になり、
「description が 1 文字」という嘘の指摘が出る。`_audit_fm` は後続のインデント行を連結する。

**このスキル自身を走査対象から外す。** `references/checklist.md` は禁止パターンの文字列を
網羅的に並べるため、走査するとレポートが自己言及の指摘で埋まる。`AUDIT_EXCLUDE_RE` の既定で
外してある。検査を追加して動作を確かめたいときだけ `AUDIT_EXCLUDE_RE='^$'` を渡す。

**`hooks/` は `*.md` を持たない。** 33 本すべてが `*.sh` である。Markdown だけを走査すると
`hooks/` は既定の対象に入っていても一度も検査されない。フックは注意文をモデルの文脈へ
注入するため中の日本語はルール本文と同じプロンプト面であり、`*.sh` も走査対象に含めてある。
シェルコードの行はコマンドとバッククォートを含むため、`_AUDIT_TOOL_LINE_RE` の除外が
そのまま雑音を落とす。

**`grep -c` は 0 件のとき終了コード 1 を返す。** `audit_report` の集計で
`set -e` 下に置くとレポートが途中で切れる。`|| true` を付けてある。

## 依存

`bash` / `awk` / `grep` / `find` / `sort`。`jq` があると
`skills/agent-routing/data/roles.json` のロール別 effort まで検査する。無ければその検査だけ飛ばす。
