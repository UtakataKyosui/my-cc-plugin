#!/usr/bin/env bash
# obsidian-semantic-search のセットアップ: プラグイン内に venv を作り依存を導入する。
# uv があれば uv、無ければ python3 -m venv + pip にフォールバックする。冪等。
set -euo pipefail

# プラグインルート（このスクリプトの位置）を基準にする。
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
VENV_DIR="${PLUGIN_ROOT}/.venv"
REQ="${PLUGIN_ROOT}/requirements.txt"

echo "[setup] plugin root: ${PLUGIN_ROOT}"

if command -v uv >/dev/null 2>&1; then
  echo "[setup] uv を使用します"
  uv venv "${VENV_DIR}"
  uv pip install --python "${VENV_DIR}/bin/python" -r "${REQ}"
else
  echo "[setup] uv が無いため python3 -m venv を使用します"
  python3 -m venv "${VENV_DIR}"
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip
  "${VENV_DIR}/bin/python" -m pip install -r "${REQ}"
fi

echo "[setup] 埋め込みモデルの事前ダウンロードを確認します（初回は時間がかかります）..."
MODEL_NAME="${OBSIDIAN_SEMANTIC_MODEL:-intfloat/multilingual-e5-small}"
"${VENV_DIR}/bin/python" - "${MODEL_NAME}" <<'PY'
import sys
from sentence_transformers import SentenceTransformer
name = sys.argv[1]
print(f"[setup] downloading/loading model: {name}")
SentenceTransformer(name)
print("[setup] model ready")
PY

echo "[setup] ready"
