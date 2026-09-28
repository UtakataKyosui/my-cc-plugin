#!/usr/bin/env bash
set -euo pipefail

# Worktree 環境整備スクリプト（個人グローバル版 / ~/.claude/scripts）
# 使用方法: bash ~/.claude/scripts/setup-worktree.sh [メインリポジトリのパス]
# 引数省略時は git worktree list からメインリポジトリのパスを自動検出する。
#
# 個人設定で全リポジトリに適用されるため、mise プロジェクト以外では該当処理をスキップする。
# 現状の Claude Code ベストプラクティスに照らして要再検討（issue-driven-flow-plugin と同様の見直し対象）。

if [ -n "${1:-}" ]; then
  MAIN_REPO="$1"
else
  MAIN_REPO="$(git worktree list --porcelain | grep '^worktree ' | head -1 | sed 's/^worktree //')"
fi

if [ -z "$MAIN_REPO" ] || [ ! -d "$MAIN_REPO" ]; then
  echo "エラー: メインリポジトリが見つかりません: ${MAIN_REPO:-<未検出>}" >&2
  exit 1
fi

echo "=== Worktree 環境整備を開始 ==="
echo "メインリポジトリ: $MAIN_REPO"

# 1. mise trust / install / 依存インストール（mise プロジェクトのみ）
if command -v mise >/dev/null 2>&1 && { [ -f mise.toml ] || [ -f .mise.toml ]; }; then
  echo "--- mise trust / install ---"
  mise trust
  mise install
  echo "--- 依存パッケージのインストール ---"
  mise run install || echo "  (install タスクが無い/失敗のためスキップ)" >&2
else
  echo "--- mise プロジェクトではないため依存セットアップをスキップ ---"
fi

# 2. .env / .env.local の動的検出・コピー（apps/packages がある場合のみ。空白安全のため -print0）
echo "--- .env ファイルのコピー ---"
while IFS= read -r -d '' env_file; do
  rel_path="${env_file#"$MAIN_REPO"/}"
  mkdir -p "$(dirname "$rel_path")"
  cp "$env_file" "$rel_path"
  echo "  コピー: $rel_path"
done < <(find "$MAIN_REPO/apps" "$MAIN_REPO/packages" -maxdepth 2 \( -name '.env' -o -name '.env.local' \) -print0 2>/dev/null)

# 3. .env.example からのフォールバック
echo "--- .env.example からのフォールバック ---"
while IFS= read -r -d '' example_file; do
  dir="$(dirname "$example_file")"
  target="$dir/.env"
  # .env.mock / .env.development を持つディレクトリ（dashboard 等）は .env.local を対象にする
  if [ -f "$dir/.env.mock" ] || [ -f "$dir/.env.development" ]; then
    target="$dir/.env.local"
  fi
  if [ ! -f "$target" ]; then
    cp "$example_file" "$target"
    echo "  フォールバック: $example_file -> $target"
  fi
done < <(find apps packages -maxdepth 2 -name '.env.example' -print0 2>/dev/null)

# 4. ローカル設定ファイルのコピー
echo "--- ローカル設定ファイルのコピー ---"
for local_file in .claude/settings.local.json .mcp.json; do
  if [ -f "$MAIN_REPO/$local_file" ]; then
    mkdir -p "$(dirname "$local_file")"
    cp "$MAIN_REPO/$local_file" "$local_file"
    echo "  コピー: $local_file"
  fi
done

touch .worktree-setup-done
echo "=== Worktree 環境整備が完了 ==="
