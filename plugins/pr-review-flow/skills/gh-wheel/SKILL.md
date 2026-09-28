---
name: gh-wheel
description: gh wheel 拡張で PR と Issue を操作する。task、graph、monitor、review の各コマンドでタスク管理、依存グラフの生成、レビューの投稿と返信を行う。Issue 駆動開発の進行状況を確認したいとき、PR レビューを投稿したいときに使う。
allowed-tools: Bash(gh wheel *)
---

# gh-wheel

gh-wheel integrates task management, issue relationship graphs,
and code review workflows into a single gh extension.

  gh wheel task     — browse and manage your PRs and Issues
  gh wheel graph    — visualize Issue/PR dependency graphs
  gh wheel monitor  — watch multiple repos in a live TUI
  gh wheel review   — AI-assisted code review workflows

このスキルは `gh wheel` CLI を操作するためのリファレンスです。以下のコマンドを実行して gh-wheel を操作してください。

## コマンドリファレンス

### `gh wheel graph`

Visualize GitHub Issue/PR relationship graphs

Fetch and display dependency and reference graphs between Issues and PRs.

Examples:
  # Show the full repository graph as a list
  gh wheel graph

  # Show a BFS subgraph rooted at issue #10, depth 3
  gh wheel graph --issue 10 --depth 3

  # Export graph as DOT for Graphviz
  gh wheel graph --format dot

  # Export graph as JSON
  gh wheel graph --format json

  # Filter by label
  gh wheel graph --label "bug"

```
gh wheel graph [flags]
```

フラグ:

- `--depth` — BFS depth from --issue (ignored when --issue=0) (default "2")
- `--format` — Output format: list|tree|dot|json (default "list")
- `--issue` — BFS start issue number (0 = fetch whole repo) (default "0")
- `--jq` — jq filter applied to JSON output
- `--label` — Filter nodes by label
- `--milestone` — Filter nodes by milestone title
- `--no-sub-issues` — Skip sub-issue queries
- `--no-timeline` — Skip cross-reference timeline queries

### `gh wheel review`

Code review workflows for GitHub PRs

Generate review prompts, validate AI review output, and post structured code reviews.

#### `gh wheel review post`

Post a structured review (JSON/YAML) to a GitHub PR

Validate and post an AI-generated structured review file to a GitHub Pull Request.

```
gh wheel review post <PR> -f <file> [flags]
```

フラグ:

- `--dry-run` — Print payload JSON without posting to GitHub
- `-f, --file` — Path to the review JSON/YAML file (required)
- `--format` — File format: yaml|json (default: auto-detect by extension)
- `--min-comments` — Minimum comment count (0 = use default of 1) (default "0")
- `--repo` — Repository (owner/name), defaults to current directory
- `--strict` — Treat warnings as errors

#### `gh wheel review reply`

Post a reply to a PR review comment

Post a reply to a specific pull request review comment by comment ID.

```
gh wheel review reply <PR> [flags]
```

フラグ:

- `--body` — reply text (required)
- `--comment-id` — reply target comment ID (required)
- `-R, --repo` — repository (owner/name); defaults to cwd

#### `gh wheel review schema`

Print the JSON Schema for review output to stdout

```
gh wheel review schema
```

#### `gh wheel review threads`

List unresolved review threads for a pull request

Fetches all review threads for the given PR and prints the ones that are neither resolved nor outdated.

```
gh wheel review threads <PR> [flags]
```

フラグ:

- `--json` — Output as JSON
- `-R, --repo` — Repository (OWNER/REPO). Defaults to current directory's repo.

#### `gh wheel review validate`

Validate an AI-generated review JSON/YAML file before posting

Gate-keeper that validates AI-generated review JSON/YAML before posting to GitHub.

```
gh wheel review validate -f <file> [flags]
```

フラグ:

- `-f, --file` — Path to the review JSON/YAML file (required)
- `--format` — File format: yaml|json (default: auto-detect by extension)
- `--min-comments` — Override minimum comment count (0 = use dynamic) (default "0")
- `--pr` — PR number (used to fetch changed_files for dynamic threshold) (default "0")
- `--repo` — Repository (owner/name), defaults to current directory
- `--strict` — Treat warnings as errors

### `gh wheel task`

Manage your GitHub tasks (PRs and Issues)

Browse and operate on PRs and Issues you are involved in as author or reviewer.

```
gh wheel task [flags]
```

フラグ:

- `-a, --author-only` — Show only PRs where you are the author
- `-d, --include-drafts` — Include draft PRs (default "true")
- `--issues-only` — Show only Issues (implies --with-issues)
- `-r, --review-only` — Show only PRs where review is requested from you
- `-s, --state` — Filter by state: open, closed, all (default "open")
- `-I, --with-issues` — Include Issues assigned to you
- `--with-reviews` — Fetch review status for each PR (slower)

#### `gh wheel task close`

Close a PR or Issue by number

Close the PR or Issue with the given number.

By default the command prints the item's title, state, and URL, then asks you
to re-enter the number as a confirmation before closing.  Pass --json to skip
the confirmation and close immediately.

```
gh wheel task close <N>
```

#### `gh wheel task prompt`

Output a Markdown review prompt for a PR to stdout

Fetch PR metadata and diff, then write a Markdown prompt suitable
for AI review to stdout.

Example:
  gh wheel task prompt 123 | claude --print > review.json

```
gh wheel task prompt <PR>
```

## グローバルフラグ

すべてのサブコマンドで利用できます。

- `--dry-run` — Validate input without sending API requests
- `--jq` — Filter JSON output with a jq expression
- `-j, --json` — Output results as JSON
- `--no-report` — Do not offer to file an issue when an unexpected error occurs
- `-R, --repo` — Repository in owner/repo format (detected from cwd if omitted)

## 補足

- `--json` を付けると機械可読な JSON を stdout に出力します。スクリプトや AI 連携ではこちらを使ってください。
- `--jq <式>` で JSON 出力を絞り込めます。
- `--repo owner/repo` で対象リポジトリを明示できます（省略時は cwd から検出）。
- 予期しないエラーや panic が発生すると、対話実行時に gh-wheel への Issue 起票（auto-report）が提案されます。`--no-report` または環境変数 `GH_WHEEL_NO_REPORT` で抑止できます。
