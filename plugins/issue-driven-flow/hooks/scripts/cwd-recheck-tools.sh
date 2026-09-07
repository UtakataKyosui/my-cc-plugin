#!/bin/bash
# CwdChanged hook: ディレクトリ移動後に harness-toolkit 必須ツールの可用性を再確認する
# check-tools.sh の軽量版（必須ツールのみ、短いタイムアウト）
# 常に exit 0（絶対にブロックしない）
set -uo pipefail

# 必須ツールのみチェック（オプションツールは SessionStart の check-tools.sh に任せる）
REQUIRED_TOOLS=("fd" "rg")
MISSING=()

for tool in "${REQUIRED_TOOLS[@]}"; do
  if ! command -v "$tool" &>/dev/null; then
    MISSING+=("$tool")
  fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "harness-toolkit [cwd]: 必須ツールが見つかりません: ${MISSING[*]}" >&2
  echo "  → harness-setup エージェントでインストール手順を確認してください" >&2
fi

exit 0
