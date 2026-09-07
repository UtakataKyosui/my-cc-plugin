#!/bin/bash
# CwdChanged hook: ディレクトリ移動時に mise で必要なツールの未インストール分を検出する
# 常に exit 0（advisory のみ、ブロックしない）
set -uo pipefail

# mise が利用可能か確認
if ! command -v mise &>/dev/null; then
  exit 0
fi

# .mise.toml または .tool-versions が存在するか確認
if [ ! -f ".mise.toml" ] && [ ! -f ".tool-versions" ]; then
  exit 0
fi

# 未インストールのツールを確認
MISSING=$(mise ls --missing 2>/dev/null || echo "")
if [ -z "$MISSING" ]; then
  exit 0
fi

echo "[mise] 未インストールのツールが見つかりました:" >&2
echo "$MISSING" | while IFS= read -r line; do
  echo "  $line" >&2
done
echo "  → mise install で必要なツールをインストールできます" >&2

exit 0
