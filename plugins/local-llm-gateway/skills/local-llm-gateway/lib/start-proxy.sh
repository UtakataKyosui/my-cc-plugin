#!/usr/bin/env bash
# ローカルLLM(Ollama)をClaude Code向けにAnthropic互換で公開するLiteLLM proxyを起動する。
# 罠: ollama/<model> ではなく ollama_chat/<model> を使うこと。
#   generate エンドポイント(ollama/)はツール呼び出し(function calling)を返さず、
#   Claude Code が期待する tool_use ブロックが得られないため必ず ollama_chat/ を使う。
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${LITELLM_PROXY_PORT:-4000}"
KEY_FILE="${LITELLM_LOCAL_KEY_FILE:-$HOME/.config/litellm-local/master.key}"

WAITED=0
until curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do
  if [ "$WAITED" -ge 60 ]; then
    echo "Ollama が60秒待っても起動しません。'ollama serve' を確認してください。" >&2
    exit 1
  fi
  sleep 2
  WAITED=$((WAITED + 2))
done

mkdir -p "$(dirname "$KEY_FILE")"
if [ ! -f "$KEY_FILE" ]; then
  (umask 077; echo "sk-local-$(openssl rand -hex 16)" > "$KEY_FILE")
  echo "マスターキーを生成しました: $KEY_FILE"
fi
export LITELLM_MASTER_KEY
LITELLM_MASTER_KEY="$(cat "$KEY_FILE")"

exec litellm --config "${SKILL_DIR}/config.yaml" --port "${PORT}"
