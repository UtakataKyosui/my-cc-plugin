---
name: claude-config-doctor
description: ~/.claude の Rules / Skills / Hooks / Agents と有効プラグインの整合性を機械的に検査する。settings.json に登録されたフックの実体と timeout、hooks/ の孤立ファイル、rules と skills からの壊れた参照、SKILL.md と agents の frontmatter、プラグインの hooks.json と agents/ 構成を一括で調べる。「設定を棚卸しして」「フックが動いているか確認して」「rules と skills の整合性を見て」と言われたとき、Rules や Hooks を追加・削除した直後に使う。
---

# claude-config-doctor

## 実行

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/claude-config-doctor/lib/doctor.py
python3 ${CLAUDE_PLUGIN_ROOT}/skills/claude-config-doctor/lib/doctor.py --json   # 機械処理向け
python3 ${CLAUDE_PLUGIN_ROOT}/skills/claude-config-doctor/lib/doctor.py --root /path/to/dotclaude
```

手動実行時は `${CLAUDE_PLUGIN_ROOT}` を `~/.claude/plugins/installed_plugins.json` の
`installPath` に置き換える。`--root` の既定値は検査対象の `~/.claude` であり、
このスキル自身の置き場とは別物なので変更していない。

問題が 1 件以上あれば終了コード 1 を返す。出力は 1 行 1 件で `[owner] kind target: message` の形。owner は dotclaude か、プラグインの配布元リポジトリ名になる。

## 検査項目

| kind | 内容 |
|---|---|
| hook-missing / hook-not-executable | settings.json とプラグイン hooks.json の command が指すファイルの存在と実行権限 |
| hook-timeout-unit | timeout が 600 を超える。公式仕様の単位は秒で既定 600 秒。ミリ秒で書くと実質無制限になる |
| hardcoded-home | command に /Users/xxx/ のような絶対パスが入っている |
| hook-orphan / hook-unregistered | hooks/ にあるが settings.json から参照されていない。orphan はどこからも言及がない |
| broken-ref | rules・skills・agents・commands の本文でバッククォートされた rules/ skills/ hooks/ agents/ パスが存在しない |
| stale-mention | 廃止・移行済みの名前（gh my-task、cmux、junct-* Skill など）への言及 |
| skill-no-skillmd / skill-no-frontmatter / skill-name-mismatch / skill-no-description | SKILL.md の存在と frontmatter |
| skill-model-effort | SKILL.md に model か effort がある。disable-model-invocation の Skill の effort は許す |
| skill-symlink / skill-gitignored | skills/ 配下がシンボリックリンクか gitignore されていて、他マシンで再現しない |
| agent-no-model / agent-bad-key | agents/*.md の model 未指定、disallowed-tools のケバブケース |
| plugin-agent-not-agent | プラグインの agents/ に frontmatter のない .md がある。全ツール許可のエージェントとして登録される |
| plugin-skill-no-description / plugin-command-no-description | プラグインの Skill と command の description が空 |

## 判明している罠

- macOS には `timeout` コマンドがない。フックを一括で試走するときは `timeout` を使わず、`bash hook.sh < input.json` を直接回す
- プラグインキャッシュ（~/.claude/plugins/cache/）の hooks.json は `$CLAUDE_PLUGIN_ROOT` のまま保存されている。展開は実行時に行われるため、キャッシュの内容をそのまま絶対パス判定にかけると全件が誤検出になる。判定は展開前の文字列に対して行う
- プラグイン側の Skill は `description: >` や `description: |` の複数行形式が多い。frontmatter の 1 行パーサで空判定すると誤検出するため、キーの存在だけを見る
- `jj safe-new` は lefthook 設定のないリポジトリでも `jj fix` のゲートで失敗することがある（jj-exec-aliases #57）。`JJ_FIX_LEFTHOOK_CMD='true {file}'` で lint を素通しにできる
- rules/junct-time-tracking.md のようにプラグイン相対パスを書いている行は broken-ref から除外する。行に「プラグイン」か plugin が含まれていれば飛ばす

## 依存

python3 のみ。git と jj は check-ignore の判定にだけ使い、なければその検査を飛ばす。
