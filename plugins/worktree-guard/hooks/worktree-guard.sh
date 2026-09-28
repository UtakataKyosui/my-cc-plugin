#!/bin/bash
# worktree-guard.sh - SessionStart hook
# 並行 Claude Code セッションが同じ作業ディレクトリで動作していることを検出し、
# Git Worktree / jj workspace への移行を促す。

set -euo pipefail

MY_CWD="$(pwd -P)"

# 自セッションの claude は hook の直接の親とは限らない（/bin/sh -c を挟む）ため、祖先をすべて除外対象にする
ANCESTORS=" "
_p=$$
while [ -n "$_p" ] && [ "$_p" -gt 1 ]; do
  ANCESTORS="${ANCESTORS}${_p} "
  _p=$(ps -o ppid= -p "$_p" 2>/dev/null | tr -d ' ' || true)
done

# 既に worktree 内なら検出不要
if echo "$MY_CWD" | grep -q '/.claude/worktrees/'; then
  echo '{}'
  exit 0
fi

# jj workspace が default 以外なら既に分離済み
if [ -d "$MY_CWD/.jj" ]; then
  JJ_WS=$(jj workspace list 2>/dev/null | grep '(current)' | awk '{print $1}' || echo "default:")
  if [ "$JJ_WS" != "default:" ]; then
    echo '{}'
    exit 0
  fi
fi

# 並行 Claude セッションを検出
# ps -eo pid,args でメインプロセスのみ抽出（MCP server, hook, shell は除外）
PARALLEL_COUNT=0

# PID と引数は read で分ける。1 行ごとに awk や cut を起動すると、数百プロセスで timeout の 5 秒を超える
while read -r PID ARGS; do
  # 自セッション（hook の祖先プロセス）をスキップ
  [[ "$ANCESTORS" == *" $PID "* ]] && continue

  # メインの Claude CLI プロセスのみ対象
  # コマンドが "claude" で始まるもの（フルパス含む）
  # python3, node, bash, sh, zsh などのサブプロセスは除外
  case "$ARGS" in
    claude|*/claude|claude\ *|*/claude\ *) ;;  # OK: メインプロセス（引数なし起動を含む）
    *) continue ;;              # NG: サブプロセス
  esac

  # プロセスの cwd を lsof で取得
  PROC_CWD=$(lsof -p "$PID" -a -d cwd -Fn 2>/dev/null | grep '^n' | sed 's/^n//' || echo '')

  if [ "$PROC_CWD" = "$MY_CWD" ]; then
    PARALLEL_COUNT=$((PARALLEL_COUNT + 1))
  fi

  # タイムアウト防止: 最大 10 件で打ち切り
  [ "$PARALLEL_COUNT" -ge 10 ] && break

done < <(ps -eo pid,args 2>/dev/null | grep -v '^[[:space:]]*PID' || true)

# 並行セッションなし → silent exit
if [ "$PARALLEL_COUNT" -eq 0 ]; then
  echo '{}'
  exit 0
fi

# VCS 種別を判定
if [ -d "$MY_CWD/.jj" ]; then
  VCS_MSG="jj リポジトリが検出されました。\`jj workspace add .claude/worktrees/<name> --name <name>\` で workspace を作成するか、EnterWorktree ツールを使用してください。"
elif [ -d "$MY_CWD/.git" ]; then
  VCS_MSG="Git リポジトリが検出されました。EnterWorktree ツールで Git Worktree に移行してください。"
else
  VCS_MSG="EnterWorktree ツールまたは手動でディレクトリを分離してください。"
fi

# additionalContext を出力
jq -n \
  --arg count "$PARALLEL_COUNT" \
  --arg cwd "$MY_CWD" \
  --arg vcs "$VCS_MSG" \
  '{
    hookSpecificOutput: {
      hookEventName: "SessionStart",
      additionalContext: ("WORKTREE-GUARD: " + $count + " 件の並行 Claude Code セッションがこのディレクトリ (" + $cwd + ") で動作中です。ファイル競合を防ぐため、編集を開始する前に必ず isolated workspace に移行してください。\n\n" + $vcs + "\n\n移行せずにファイルを編集すると他のセッションと競合する可能性があります。/worktree-guard skill で対話的に設定できます。")
    }
  }'
