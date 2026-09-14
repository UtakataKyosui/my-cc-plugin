#!/usr/bin/env bash
# local-llm-gateway の自己診断。Ollama起動・proxy疎通・/v1/messages応答を順に確認する。
set -uo pipefail

PORT="${LITELLM_PROXY_PORT:-4000}"
KEY_FILE="${LITELLM_LOCAL_KEY_FILE:-$HOME/.config/litellm-local/master.key}"

ok() { echo "OK   $1"; }
ng() { echo "NG   $1"; }

if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
  ok "Ollama が起動している (http://localhost:11434)"
else
  ng "Ollama に接続できません。'ollama serve' を実行してください"
  exit 1
fi

OLLAMA_MODELS="$(ollama list 2>/dev/null)"
if echo "$OLLAMA_MODELS" | grep -q '^gemma4:26b'; then
  ok "モデル gemma4:26b が pull 済み"
else
  ng "gemma4:26b が見つかりません。'ollama pull gemma4:26b' を実行してください"
  exit 1
fi

if [ -f "$KEY_FILE" ]; then
  ok "マスターキーファイルが存在する ($KEY_FILE)"
else
  ng "マスターキーファイルが未生成 ($KEY_FILE)。start-proxy.sh を一度実行してください"
fi

if curl -sf "http://localhost:${PORT}/health/readiness" >/dev/null 2>&1; then
  ok "LiteLLM proxy が http://localhost:${PORT} で応答している"
else
  ng "LiteLLM proxy に接続できません。lib/start-proxy.sh を実行してください"
  exit 1
fi

if [ -f "$KEY_FILE" ]; then
  KEY="$(cat "$KEY_FILE")"
  RESP=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${PORT}/v1/messages" \
    -H "x-api-key: ${KEY}" -H "anthropic-version: 2023-06-01" -H "content-type: application/json" \
    -d '{"model":"gemma4-26b","max_tokens":16,"messages":[{"role":"user","content":"ping"}]}')
  if [ "$RESP" = "200" ]; then
    ok "/v1/messages が gemma4-26b で 200 を返した"
  else
    ng "/v1/messages が HTTP ${RESP} を返した(proxyログを確認)"
    exit 1
  fi
fi
