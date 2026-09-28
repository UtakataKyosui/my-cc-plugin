# worktree-guard

並行 Claude Code セッションを検出し、Git Worktree / jj workspace で作業を分離する。

## 構成

| 種別 | パス | 役割 |
|---|---|---|
| Skill | `skills/worktree-guard/SKILL.md` | 対話的に分離方法を確認し、workspace/worktree を作成する手順 |
| Hook (SessionStart) | `hooks/worktree-guard.sh` | セッション開始時に、同じ作業ディレクトリで動く並行 Claude セッションを検出し、検出したら additionalContext で警告する |
| Hook (PostToolUse: `Bash\|EnterWorktree`) | `hooks/setup-worktree-auto.sh` | `git worktree add` や EnterWorktree で worktree が作られたことを検出し、環境整備スクリプトを自動実行する |

## 前提条件

`hooks/setup-worktree-auto.sh` は、worktree 作成を検出した後に `$HOME/.claude/scripts/setup-worktree.sh` を呼び出す。このスクリプトは配布物に含まれない個人環境固有のセットアップ処理（依存関係のインストールなど）を想定したもので、このプラグインをインストールする環境ごとに用意する必要がある。存在しない場合、`setup-worktree-auto.sh` は worktree 作成後にエラーで終了する。

環境整備を必要としない場合は、`hooks/hooks.json` から `PostToolUse` のエントリを削除するか、`$HOME/.claude/scripts/setup-worktree.sh` を空スクリプト（`#!/bin/bash` のみ）として用意する。
