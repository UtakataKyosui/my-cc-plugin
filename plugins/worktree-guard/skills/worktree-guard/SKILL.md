---
name: worktree-guard
description: 並行 Claude Code セッションを検出し、Git Worktree / jj workspace で作業を分離してファイル競合を防止する。VCS 種別（jj 優先 / git）を自動判定し、分離方法をユーザーに確認してから workspace/worktree を作成する。
when_to_use: 「並行セッションを確認して」「worktree に移動して」と指示されたとき。SessionStart hook が並行セッションを検出して警告を出したとき。ファイル競合が発生したとき。
allowed-tools: Bash(jj workspace *) Bash(jj log *) Bash(jj status *) Bash(jj bookmark list *) Bash(jj bookmark rename *) Bash(jj git fetch *) Bash(git worktree *) Bash(git status *) Bash(git branch *) Bash(git fetch *)
---

# Worktree Guard

並行 Claude Code セッションを検出し、Git Worktree または jj workspace で作業を分離する。このプラグインには SessionStart / PostToolUse で自動検出するフック（`hooks/worktree-guard.sh`、`hooks/setup-worktree-auto.sh`）が同梱されている。フックの詳細は README を参照する。

## ワークフロー

### Step 1: 並行セッションを検出する

```bash
ps -eo pid,args 2>/dev/null | while IFS= read -r line; do
  PID=$(echo "$line" | awk '{print $1}')
  ARGS=$(echo "$line" | cut -d' ' -f2-)
  # メイン Claude CLI のみ（サブプロセスは除外）
  case "$ARGS" in
    claude\ *|*/claude\ *) ;;
    *) continue ;;
  esac
  [ "$PID" = "$PPID" ] && continue
  PROC_CWD=$(lsof -p "$PID" -a -d cwd -Fn 2>/dev/null | grep '^n' | sed 's/^n//' || echo '')
  [ "$PROC_CWD" = "$PWD" ] && echo "  PID=$PID  $ARGS"
done
```

注意: `ps` はサンドボックス外でのみ実行可能。Bash ツールで実行が拒否された場合はサンドボックスを一時的に無効にする。

- 出力がなければ「並行セッションは検出されませんでした。安全に作業できます。」と報告して終了
- 出力があれば Step 2 へ

### Step 2: VCS 種別を判定する

- `.jj/` ディレクトリが存在する → jj リポジトリ（jj workspace を優先）
- `.git/` ディレクトリのみ → Git リポジトリ
- 両方存在（colocated）→ jj を優先

現在の workspace / worktree 状態も確認する:
- jj: `jj workspace list`
- git: `git worktree list`

既に worktree / workspace 内なら「既に分離済みです」と報告して終了。

### Step 3: 分離方法を AskUserQuestion で確認する

検出した並行セッション数と VCS 種別を伝え、以下の選択肢を提示する:

**jj リポジトリの場合:**
1. `jj workspace add` で jj workspace を作成する（推奨）
2. EnterWorktree で Git worktree を作成する
3. 分離せずに続ける（リスクを承知の上で）

**Git リポジトリの場合:**
1. EnterWorktree で Git worktree を作成する（推奨）
2. 分離せずに続ける（リスクを承知の上で）

### Step 4: workspace / worktree を作成する

**EnterWorktree を使用する場合:**
EnterWorktree ツールを呼び出す。`name` にはタスクの内容を反映した短い名前を指定する（例: `feature-1234-add-login`）。

**jj workspace を使用する場合:**
```bash
WORKSPACE_NAME="session-$(date +%Y%m%d-%H%M%S)"
jj workspace add ".claude/worktrees/${WORKSPACE_NAME}" --name "${WORKSPACE_NAME}"
```
作成後、そのディレクトリで作業を継続する。

### Step 5: 分離を確認して報告する

作成後に `git worktree list` または `jj workspace list` で状態を確認し、「workspace が作成されました。安全に作業を開始できます。」と報告する。

## 注意事項

- worktree / workspace の削除は `git worktree remove` または `jj workspace forget` + `rm -rf` で行う
- `.claude/worktrees/` ディレクトリがプロジェクトの `.gitignore` に含まれているか確認すること
