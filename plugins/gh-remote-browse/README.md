# gh-remote-browse

リポジトリをクローンせずに、リモートのファイル内容とディレクトリ構成を読むためのプラグイン。

## 構成

| 種別 | 名前 | 役割 |
|---|---|---|
| Skill | `gh-remote-browse:gh-remote-browse` | `gh repo read-file` / `read-dir` / git trees API をまとめたシェル関数群 |
| Agent | `remote-repo-researcher` | 読み取り専用で他リポジトリを調査し、必要な箇所だけを報告する |

## 使い方

```bash
source "${CLAUDE_PLUGIN_ROOT}/skills/gh-remote-browse/lib/gh-remote.sh"
ghr_check_deps
ghr_tree owner/repo
```

ライブラリの置き場所は `GH_REMOTE_LIB` で上書きできる。

## 依存

- `gh`（GitHub CLI、認証済み）
- `jq`
